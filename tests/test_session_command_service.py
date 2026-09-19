from __future__ import annotations

from uagent.runtime.session_command_service import SessionCommandService


class _Store:
    def search(self, query, *, project=None):
        assert query == "needle"
        assert project == "demo"
        return [
            {
                "session_id": "s1",
                "created_at": "2025-01-02T00:00:00",
                "role": "user",
                "content": "first hit",
            },
            {
                "session_id": "s1",
                "created_at": "2025-01-03T00:00:00",
                "role": "assistant",
                "content": "second hit",
            },
            {
                "session_id": "s2",
                "created_at": "2025-02-01T00:00:00",
                "role": "user",
                "content": "other hit",
            },
        ]

    def list_sessions(self):
        return [
            {
                "session_id": "s1",
                "project": "demo",
                "message_count": 2,
                "summary": "summary 1",
            },
            {
                "session_id": "s2",
                "project": "demo",
                "message_count": 1,
                "summary": "summary 2",
            },
        ]


class _StateStore:
    def latest_tool_context(self, session_id):
        assert session_id == "s1"
        return {"browser": {"url": "https://example.test"}}

    def latest_response_state(self, session_id):
        assert session_id == "s1"
        return {
            "provider": "openai",
            "model": "gpt-5.4",
            "response_id": "resp_1",
            "status": "completed",
        }

    def get_agent_state(self, session_id):
        assert session_id == "s1"
        return {
            "mcp_request_generation": 4,
            "mcp_provider": "openai",
            "mcp_model": "gpt-5.4",
        }


def test_plan_summarize_filters_explicit_target_and_bounds_bulk_work() -> None:
    rows = [{"session_id": f"session-{index}"} for index in range(12)]

    bulk = SessionCommandService.plan_summarize(rows, limit=10)
    targeted = SessionCommandService.plan_summarize(rows, target="session-11", limit=10)

    assert len(bulk.rows) == 10
    assert targeted.rows == ({"session_id": "session-11"},)
    assert len(rows) == 12


def test_plan_prune_excludes_active_session_without_mutating_rows() -> None:
    rows = [
        {"session_id": "new"},
        {"session_id": "old"},
        {"session_id": "active"},
    ]

    plan = SessionCommandService.plan_prune(rows, 1, active_session_id="active")

    assert plan.keep == 1
    assert [row["session_id"] for row in plan.candidates] == ["old"]
    assert len(rows) == 3


def test_plan_prune_keeps_all_rows_when_keep_exceeds_history() -> None:
    plan = SessionCommandService.plan_prune([{"session_id": "only"}], 10)

    assert plan.candidates == ()


def test_plan_workdir_validates_message_path_without_changing_cwd(tmp_path) -> None:
    current = str(tmp_path / "current")
    target = tmp_path / "target"
    target.mkdir()

    plan = SessionCommandService.plan_workdir(
        "s1",
        message_workdir=str(target),
        current_workdir=current,
    )

    assert plan is not None
    assert plan.target_path == str(target)
    assert plan.previous_path == current


def test_plan_workdir_falls_back_to_project_path_and_rejects_missing_path(
    tmp_path,
) -> None:
    target = tmp_path / "project"
    target.mkdir()

    assert SessionCommandService.plan_workdir(
        "s1", session_project_path=str(target), current_workdir="previous"
    ).target_path == str(target)
    assert (
        SessionCommandService.plan_workdir(
            "s1", message_workdir=str(tmp_path / "missing")
        )
        is None
    )


def test_build_restore_plan_adds_missing_system_prompt_without_mutating_input() -> None:
    messages = [{"role": "user", "content": "hello"}]
    state = SessionCommandService(_StateStore()).load_context_state("s1")

    plan = SessionCommandService(_StateStore()).build_restore_plan(
        "s1",
        messages,
        system_prompt="system",
        state=state,
    )

    assert messages == [{"role": "user", "content": "hello"}]
    assert plan.messages[0] == {"role": "system", "content": "system"}
    assert plan.tool_context == state.tool_context
    assert plan.response_state == state.response_state
    assert plan.agent_state == state.agent_state


def test_resolve_load_target_prefers_search_result_index() -> None:
    sessions = [{"session_id": "session-0"}, {"session_id": "session-1"}]

    result = SessionCommandService.resolve_load_target(
        "0", sessions, search_results={0: "search-session"}
    )

    assert result.target == "search-session"
    assert result.error is None


def test_resolve_load_target_uses_session_index_and_reports_invalid_index() -> None:
    sessions = [{"session_id": "session-0"}, {"session_id": "session-1"}]

    assert (
        SessionCommandService.resolve_load_target("1", sessions).target == "session-1"
    )
    assert (
        SessionCommandService.resolve_load_target("9", sessions).error
        == "index_out_of_range"
    )
    assert (
        SessionCommandService.resolve_load_target("session-1", sessions).target
        == "session-1"
    )


def test_load_context_state_returns_persisted_runtime_state() -> None:
    state = SessionCommandService(_StateStore()).load_context_state("s1")

    assert state.tool_context == {"browser": {"url": "https://example.test"}}
    assert state.response_state["response_id"] == "resp_1"


def test_load_context_state_degrades_when_optional_state_is_unavailable() -> None:
    class _Unavailable:
        def latest_tool_context(self, session_id):
            raise RuntimeError("missing")

        def latest_response_state(self, session_id):
            raise RuntimeError("missing")

    state = SessionCommandService(_Unavailable()).load_context_state("s1")

    assert state.tool_context == {}
    assert state.response_state is None


def test_search_projects_message_hits_into_sorted_session_rows() -> None:
    results = SessionCommandService(_Store()).search(
        "needle",
        project="demo",
    )

    assert [result.row["session_id"] for result in results] == ["s2", "s1"]
    assert results[0].matches == 1
    assert results[0].hit_role == "user"
    assert results[0].hit_content == "other hit"
    assert results[1].matches == 2
    assert results[1].row["summary"] == "summary 1"
    assert results[1].row["created_at"] == "2025-01-03T00:00:00"
    assert results[1].hit_role == "user"
    assert results[1].hit_content == "first hit"


def test_search_sort_keys_are_applied_by_service() -> None:
    results = SessionCommandService(_Store()).search(
        "needle",
        project="demo",
        sort_keys=("matches",),
    )

    assert [result.row["session_id"] for result in results] == ["s1", "s2"]
