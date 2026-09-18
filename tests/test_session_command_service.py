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
