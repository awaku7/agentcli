from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from types import SimpleNamespace

import pytest

from uagent.runtime.compaction_record import (
    CompactionRecord,
    CompactionValidationError,
    GoalDelta,
    ProvenancedObservation,
    SourceRef,
)
from uagent.runtime.session_store import SessionStore, SessionStoreError
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.tools import sub_agent_tool
from uagent.tools.context import ToolCallbacks


def _main(store):
    session = store.create_session(project="test", entry_point="cli")
    store.append_message(session.session_id, "user", "PRIVATE MAIN HISTORY")
    item = store.list_indexed_messages(session.session_id)[0]
    ref = SourceRef("message", item["ref_id"], session.session_id, item["session_seq"])
    store.commit_compaction_record(
        CompactionRecord(
            record_id="checkpoint",
            operation_id="operation",
            application_status="applied",
            session_id=session.session_id,
            actor_kind="runtime",
            actor_id="test",
            source_start_seq=1,
            source_end_seq=1,
            base_revision=0,
            goal_deltas=(
                GoalDelta(
                    goal_delta_id="delta",
                    association="new",
                    title_hint="Investigate regression",
                    progress_events=(
                        ProvenancedObservation("Reproduced regression", (ref,)),
                    ),
                    source_refs=(ref,),
                ),
            ),
        )
    )
    goal_id = next(
        iter(
            store.get_agent_state(session.session_id)["structured_compaction"]["goals"]
        )
    )
    return session.session_id, goal_id, ref


def _dispatch(store, session_id, goal_id, ref, **changes):
    kwargs = dict(
        receiving_session_id=session_id,
        objective="Inspect regression",
        task_scope="Read-only investigation",
        goal_ids=(goal_id,),
        source_refs=(ref,),
        source_access_check=lambda source: source == ref,
    )
    kwargs.update(changes)
    return capture_sub_agent_dispatch(store, **kwargs)


def test_snapshot_and_output_provenance_survive_reopen_without_main_mutation(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path) as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        context = dispatch.render_context()
        assert "Reproduced regression" in context
        assert "PRIVATE MAIN HISTORY" not in context
        assert dispatch.bounds.receiving_base_revision == 1
        store.save_agent_state(
            session_id, {"memory": "PRIVATE MEMORY"}, expected_revision=1
        )
        assert dispatch.render_context() == context
        assert dispatch.bounds.receiving_base_revision == 1
        before = store.get_agent_state_snapshot(session_id)
        output_ref = dispatch.record_result(
            '{"status":"completed","summary":"Found cause"}'
        )
        assert store.get_agent_state_snapshot(session_id) == before
        assert len(store.list_indexed_messages(session_id)) == 1
    with SessionStore(path) as reopened:
        messages = reopened.list_indexed_messages(dispatch.source_session_id)
        assert len(messages) == 2
        assert messages[0]["payload"]["receiving_base_revision"] == 1
        assert messages[0]["payload"]["receiving_session_id"] == session_id
        assert messages[1]["ref_id"] == output_ref.ref_id
        assert messages[1]["session_seq"] == output_ref.session_seq
        assert output_ref.scope_id == dispatch.source_session_id
        assert messages[1]["payload"]["dispatch_id"] == dispatch.dispatch_id
        assert "Found cause" in messages[1]["content"]


def test_delivery_rechecks_authorization_and_rejects_missing_grants(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        allowed = True
        dispatch = _dispatch(
            store, session_id, goal_id, ref, source_access_check=lambda source: allowed
        )
        allowed = False
        with pytest.raises(CompactionValidationError, match="delivery"):
            dispatch.render_context()
        with pytest.raises(CompactionValidationError, match="unauthorized"):
            _dispatch(store, session_id, goal_id, ref, source_refs=())


def test_runner_uses_only_projection_and_persists_actual_output(tmp_path, monkeypatch):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        runner = sub_agent_tool.SubAgentRunner()
        runner._shared_store["old"] = "PRIVATE SHARED RESULT"
        file = tmp_path / "secret.txt"
        file.write_text("PRIVATE FILE CONTENT", encoding="utf-8")
        prompts = []

        def run_llm(**kwargs):
            prompts.append(
                runner._build_user_prompt(
                    kwargs["task"].task, kwargs["pack"], kwargs["task"].scope_files
                )
            )
            assert kwargs["cache_ttl"] == 0
            return '{"status":"completed","summary":"Found cause"}', {}, 0

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        monkeypatch.setattr(
            runner.duplicate_guard,
            "get_cached",
            lambda *args: pytest.fail("structured dispatch must not read cache"),
        )
        result = runner.run(
            "general",
            dispatch.objective,
            current_file=str(file),
            parent_goal="PRIVATE PARENT GOAL",
            load_keys=["old"],
            shared_context={"memory": "PRIVATE MEMORY"},
            cache_ttl=120,
            handoff_dispatch=dispatch,
        )
        assert "PRIVATE" not in prompts[0]
        assert "secret.txt" not in prompts[0]
        assert "Reproduced regression" in prompts[0]
        messages = store.list_indexed_messages(dispatch.source_session_id)
        assert json.loads(messages[-1]["content"]) == json.loads(result)
        assert (
            "handoff_dispatch"
            not in sub_agent_tool.TOOL_SPEC["function"]["parameters"]["properties"]
        )


def test_runner_rejects_model_dict_or_changed_objective(tmp_path):
    runner = sub_agent_tool.SubAgentRunner()
    with pytest.raises(TypeError, match="trusted runtime"):
        runner.run("general", "task", handoff_dispatch={"goal_ids": ["private"]})
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        with pytest.raises(ValueError, match="objective"):
            runner.run("general", "different task", handoff_dispatch=dispatch)


def test_runner_stops_when_access_is_revoked_during_dispatch_guards(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        allowed = True
        dispatch = _dispatch(
            store, session_id, goal_id, ref, source_access_check=lambda source: allowed
        )
        runner = sub_agent_tool.SubAgentRunner()

        original_check = runner.duplicate_guard.check_and_record

        def revoke(*args):
            nonlocal allowed
            accepted = original_check(*args)
            allowed = False
            return accepted

        monkeypatch.setattr(runner.duplicate_guard, "check_and_record", revoke)
        monkeypatch.setattr(
            runner, "_run_llm", lambda **kwargs: pytest.fail("must not call provider")
        )
        with pytest.raises(CompactionValidationError, match="delivery"):
            runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 1
        assert runner.duplicate_guard.counts == {}
        allowed = True
        monkeypatch.setattr(runner.duplicate_guard, "check_and_record", original_check)
        monkeypatch.setattr(
            runner, "_run_llm", lambda **kwargs: ('{"status":"completed"}', {}, 0)
        )
        assert (
            json.loads(
                runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
            )["status"]
            == "completed"
        )


def test_reused_runner_distinguishes_new_dispatches_but_blocks_same_dispatch(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        first = _dispatch(store, session_id, goal_id, ref)
        store.save_agent_state(session_id, {"phase": "next"}, expected_revision=1)
        newer = _dispatch(store, session_id, goal_id, ref)
        other_session = store.create_session(project="test", entry_point="cli")
        other = capture_sub_agent_dispatch(
            store,
            receiving_session_id=other_session.session_id,
            objective=first.objective,
            task_scope="Read-only investigation",
            source_access_check=lambda source: False,
        )
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs["pack"].to_json())
            return '{"status":"completed","summary":"Found cause"}', {}, 0

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        for dispatch in (first, newer, other):
            result = runner.run(
                "general", dispatch.objective, handoff_dispatch=dispatch
            )
            assert json.loads(result)["status"] == "completed"
            assert len(store.list_indexed_messages(dispatch.source_session_id)) == 2
        assert len(calls) == 3
        assert json.loads(calls[0])["receiving_base_revision"] == 1
        assert json.loads(calls[1])["receiving_base_revision"] == 2
        assert json.loads(calls[2])["receiving_session_id"] == other_session.session_id
        repeated = runner.run("general", first.objective, handoff_dispatch=first)
        assert json.loads(repeated)["status"] == "blocked"
        assert len(calls) == 3
        assert len(store.list_indexed_messages(first.source_session_id)) == 2

        changed_legacy_args = runner.run(
            "general",
            first.objective,
            parent_goal="Different legacy parent goal",
            shared_context={"changed": "legacy input"},
            handoff_dispatch=first,
        )
        assert json.loads(changed_legacy_args)["status"] == "blocked"
        assert len(calls) == 3
        assert len(store.list_indexed_messages(first.source_session_id)) == 2


def test_provider_exception_releases_reservation_for_retry(tmp_path, monkeypatch):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        runner = sub_agent_tool.SubAgentRunner()
        attempts = []

        def run_llm(**kwargs):
            attempts.append(kwargs)
            if len(attempts) == 1:
                raise RuntimeError("provider unavailable")
            return '{"status":"completed","summary":"Recovered"}', {}, 0

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        with pytest.raises(RuntimeError, match="provider unavailable"):
            runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert runner.duplicate_guard.counts == {}
        result = runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert json.loads(result)["summary"] == "Recovered"
        assert len(attempts) == 2
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 2


@pytest.mark.parametrize("commit_before_error", [False, True])
def test_persistence_retry_reuses_output_and_does_not_duplicate_source(
    tmp_path, monkeypatch, commit_before_error
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs)
            return '{"status":"completed","summary":"Finished work"}', {}, 0

        append = store.append_message

        def fail_append(*args, **kwargs):
            if commit_before_error:
                append(*args, **kwargs)
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        monkeypatch.setattr(store, "append_message", fail_append)
        with pytest.raises(RuntimeError, match="storage unavailable"):
            runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert runner.duplicate_guard.counts == {}
        monkeypatch.setattr(store, "append_message", append)
        result = runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert json.loads(result)["summary"] == "Finished work"
        assert len(calls) == 1
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 2


def test_concurrent_rejection_does_not_consume_failed_dispatch_reservation(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        reached_delivery = Event()
        resume = Event()
        worker = {}
        allowed = True

        def check(source):
            if get_ident() == worker.get("thread"):
                worker["checks"] = worker.get("checks", 0) + 1
                if worker["checks"] == 2:
                    reached_delivery.set()
                    if not resume.wait(5):
                        raise RuntimeError("test delivery barrier timed out")
            return allowed

        dispatch = _dispatch(store, session_id, goal_id, ref, source_access_check=check)
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs)
            return '{"status":"completed"}', {}, 0

        def first_call():
            worker["thread"] = get_ident()
            return runner.run("general", dispatch.objective, handoff_dispatch=dispatch)

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(first_call)
            try:
                assert reached_delivery.wait(5)
                counts = dict(runner.duplicate_guard.counts)
                duplicate = runner.run(
                    "general", dispatch.objective, handoff_dispatch=dispatch
                )
                assert json.loads(duplicate)["status"] == "blocked"
                assert runner.duplicate_guard.counts == counts
                allowed = False
            finally:
                resume.set()
            with pytest.raises(CompactionValidationError, match="delivery"):
                future.result(timeout=5)
        assert runner.duplicate_guard.counts == {}
        assert calls == []
        allowed = True
        result = runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert json.loads(result)["status"] == "completed"
        assert len(calls) == 1
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 2


def test_circular_rejection_releases_reservation_for_non_nested_retry(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs)
            return '{"status":"completed"}', {}, 0

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        token = sub_agent_tool._SUB_AGENT_CALL_CHAIN.set(("general",))
        try:
            rejected = runner.run(
                "general", dispatch.objective, handoff_dispatch=dispatch
            )
        finally:
            sub_agent_tool._SUB_AGENT_CALL_CHAIN.reset(token)
        assert "Circular" in json.loads(rejected)["message"]
        assert runner.duplicate_guard.counts == {}
        assert calls == []
        result = runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert json.loads(result)["status"] == "completed"
        assert len(calls) == 1


@pytest.mark.parametrize("structured", [False, True])
def test_provider_path_separates_main_history_logs_and_shared_store(
    tmp_path, monkeypatch, structured
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref) if structured else None
        cb = ToolCallbacks(
            log_message=lambda message: store.append_message(
                session_id, message["role"], message["content"]
            )
        )
        monkeypatch.setattr(sub_agent_tool, "get_callbacks", lambda: cb)
        monkeypatch.setattr(
            sub_agent_tool,
            "make_client",
            lambda callbacks: ("openai", object(), "test"),
        )
        monkeypatch.setattr(sub_agent_tool, "_SUB_AGENT_LOG_DIR", tmp_path / "logs")
        runner = sub_agent_tool.SubAgentRunner()
        output = json.dumps(
            {
                "status": "completed",
                "role": "general",
                "summary": "PRIVATE RESULT_MARKER",
                "details": {},
                "notes": "",
            }
        )
        monkeypatch.setattr(
            runner, "_call_with_retry", lambda *args, **kwargs: (output, 0, {})
        )
        result = runner.run(
            "general",
            "Inspect regression",
            parent_goal="PRIVATE PARENT GOAL",
            store_key="result",
            completion_regex="RESULT_MARKER",
            current_file=str(tmp_path / "missing.txt") if structured else None,
            handoff_dispatch=dispatch,
        )
        assert json.loads(result)["status"] == "completed"
        main_messages = store.list_indexed_messages(session_id)
        logs = "\n".join(
            path.read_text() for path in (tmp_path / "logs").rglob("*.jsonl")
        )
        if structured:
            assert len(main_messages) == 1
            assert "PRIVATE" not in logs
            assert "result" not in runner._shared_store
            child = store.list_indexed_messages(dispatch.source_session_id)
            assert (
                json.loads(child[-1]["content"])["summary"] == "PRIVATE RESULT_MARKER"
            )
        else:
            assert any(
                "PRIVATE RESULT_MARKER" in item["content"] for item in main_messages
            )
            assert "PRIVATE PARENT GOAL" in logs
            assert "PRIVATE RESULT_MARKER" in logs
            assert runner._shared_store["result"] == result


@pytest.mark.parametrize("structured", [False, True])
def test_job_inbox_cannot_bypass_captured_context(tmp_path, monkeypatch, structured):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref) if structured else None
        inbox = [{"sequence": 1, "message": "PRIVATE LIVE INBOX"}]
        drains = []

        def drain_messages():
            drains.append(True)
            messages = list(inbox)
            inbox.clear()
            return messages

        job = SimpleNamespace(
            raise_if_cancelled=lambda: None, drain_messages=drain_messages
        )
        monkeypatch.setattr(sub_agent_tool, "get_current_sub_agent_job", lambda: job)
        monkeypatch.setattr(
            sub_agent_tool,
            "make_client",
            lambda callbacks: ("openai", object(), "test"),
        )
        runner = sub_agent_tool.SubAgentRunner()
        prompts = []
        output = json.dumps(
            {
                "status": "completed",
                "role": "general",
                "summary": "WORK_DONE",
                "details": {},
                "notes": "",
            }
        )

        def call(*args, **kwargs):
            prompts.append(kwargs["user_prompt"])
            return output, 0, {}

        monkeypatch.setattr(runner, "_call_with_retry", call)
        result = runner.run(
            "general",
            "Inspect regression",
            completion_regex="WORK_DONE",
            max_agent_rounds=2,
            handoff_dispatch=dispatch,
        )
        assert json.loads(result)["status"] == "completed"
        if structured:
            assert len(prompts) == 1
            assert drains == []
            assert inbox
            assert "PRIVATE LIVE INBOX" not in prompts[0]
        else:
            assert len(prompts) == 2
            assert "PRIVATE LIVE INBOX" in prompts[1]
            assert len(drains) == 2


def test_pending_result_capacity_blocks_new_work_but_preserves_retry(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatches = [_dispatch(store, session_id, goal_id, ref) for _ in range(3)]
        monkeypatch.setattr(sub_agent_tool, "_MAX_PENDING_HANDOFF_RESULTS", 2)
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs)
            return '{"status":"completed","summary":"Stored later"}', {}, 0

        append = store.append_message

        def fail_append(*args, **kwargs):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        monkeypatch.setattr(store, "append_message", fail_append)
        for dispatch in dispatches[:2]:
            with pytest.raises(RuntimeError, match="storage unavailable"):
                runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        third = dispatches[2]
        with pytest.raises(RuntimeError, match="capacity"):
            runner.run("general", third.objective, handoff_dispatch=third)
        assert len(calls) == 2
        assert len(runner._pending_handoff_results) == 2
        assert runner.duplicate_guard.counts == {}
        monkeypatch.setattr(store, "append_message", append)
        first = dispatches[0]
        result = runner.run("general", first.objective, handoff_dispatch=first)
        assert json.loads(result)["status"] == "completed"
        assert len(calls) == 2
        assert len(runner._pending_handoff_results) == 1
        result = runner.run("general", third.objective, handoff_dispatch=third)
        assert json.loads(result)["status"] == "completed"
        assert len(calls) == 3


@pytest.mark.parametrize("commit_before_error", [False, True])
def test_failed_capture_removes_child_session_and_allows_clean_retry(
    tmp_path, monkeypatch, commit_before_error
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        before = store.get_agent_state_snapshot(session_id)
        append = store.append_message
        if commit_before_error:

            def fail_append(*args, **kwargs):
                append(*args, **kwargs)
                raise RuntimeError("initial handoff unavailable")

            monkeypatch.setattr(store, "append_message", fail_append)
            error = RuntimeError
        else:
            store._connection.execute(
                "CREATE TRIGGER fail_initial_handoff BEFORE INSERT ON messages "
                "BEGIN SELECT RAISE(FAIL, 'initial handoff unavailable'); END"
            )
            error = SessionStoreError
        for _ in range(2):
            with pytest.raises(error, match="initial handoff unavailable"):
                _dispatch(store, session_id, goal_id, ref)
            assert [row["session_id"] for row in store.list_sessions()] == [session_id]
            assert store.get_agent_state_snapshot(session_id) == before
        monkeypatch.setattr(store, "append_message", append)
        if not commit_before_error:
            store._connection.execute("DROP TRIGGER fail_initial_handoff")
        dispatch = _dispatch(store, session_id, goal_id, ref)
        assert len(store.list_sessions()) == 2
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 1
        assert store.get_agent_state_snapshot(session_id) == before


@pytest.mark.parametrize("max_log_files", [None, 1])
def test_profile_rebuild_excludes_child_sources_before_applying_log_limit(
    tmp_path, monkeypatch, max_log_files
):
    from uagent import profile_manager
    from uagent.providers import util_providers
    from uagent.runtime import identity_context

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setattr(identity_context, "get_current_turn_context", lambda: None)
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        older = store.create_session(project="test", entry_point="gui")
        store.append_message(older.session_id, "user", "OLDER HUMAN REQUEST")
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(
            store, session_id, goal_id, ref, objective="SUBAGENT PROJECTED INPUT"
        )
        dispatch.record_result("SUBAGENT GENERATED RESULT")
        inputs = []
        saved = []

        def extract(**kwargs):
            inputs.append(kwargs["user_prompt"])
            return json.dumps(
                {
                    "environment": {},
                    "preferences": ["Keep answers concise"],
                    "constraints": [],
                }
            )

        monkeypatch.setattr(
            util_providers, "make_client", lambda core: ("openai", object(), "test")
        )
        monkeypatch.setattr(profile_manager, "_llm_simple_text", extract)
        monkeypatch.setattr(
            profile_manager,
            "_deduplicate_profile_with_llm",
            lambda profile, **kwargs: profile,
        )
        monkeypatch.setattr(
            profile_manager,
            "save_profile",
            lambda profile, principal_id: saved.append(profile),
        )
        profile = profile_manager.profile_from_logs(
            SimpleNamespace(session_store=store), max_log_files=max_log_files
        )
        assert len(inputs) == 1
        assert "PRIVATE MAIN HISTORY" in inputs[0]
        assert "SUBAGENT PROJECTED INPUT" not in inputs[0]
        assert "SUBAGENT GENERATED RESULT" not in inputs[0]
        assert ("OLDER HUMAN REQUEST" in inputs[0]) == (max_log_files is None)
        assert saved == [profile]
        assert profile["preferences"] == ["Keep answers concise"]


def test_profile_rebuild_with_only_child_messages_skips_provider(tmp_path, monkeypatch):
    from uagent import profile_manager
    from uagent.providers import util_providers
    from uagent.runtime import identity_context

    monkeypatch.setenv("UAGENT_SESSION_BACKEND", "sqlite")
    monkeypatch.setattr(identity_context, "get_current_turn_context", lambda: None)
    monkeypatch.setattr(
        util_providers,
        "make_client",
        lambda core: pytest.fail("child sessions must not be profiled"),
    )
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session = store.create_session(project="test", entry_point="cli")
        capture_sub_agent_dispatch(
            store,
            receiving_session_id=session.session_id,
            objective="Child objective",
            task_scope="Read only",
            source_access_check=lambda source: False,
        )
        assert (
            profile_manager.profile_from_logs(SimpleNamespace(session_store=store))
            is None
        )


def test_host_can_abandon_revoked_pending_results_without_reexecution(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        authorized = True
        dispatches = [
            _dispatch(
                store,
                session_id,
                goal_id,
                ref,
                source_access_check=lambda source: authorized,
            )
            for _ in range(2)
        ]
        unrelated = capture_sub_agent_dispatch(
            store,
            receiving_session_id=session_id,
            objective="Unrelated work",
            task_scope="Read only",
            source_access_check=lambda source: True,
        )
        monkeypatch.setattr(sub_agent_tool, "_MAX_PENDING_HANDOFF_RESULTS", 2)
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs)
            return '{"status":"completed","summary":"Private pending result"}', {}, 0

        append = store.append_message

        def fail_append(*args, **kwargs):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        monkeypatch.setattr(store, "append_message", fail_append)
        for dispatch in dispatches:
            with pytest.raises(RuntimeError, match="storage unavailable"):
                runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        authorized = False
        for dispatch in dispatches:
            with pytest.raises(CompactionValidationError, match="delivery"):
                runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        with pytest.raises(RuntimeError, match="capacity"):
            runner.run("general", unrelated.objective, handoff_dispatch=unrelated)
        first, second = dispatches
        assert runner.discard_pending_handoff_result(first) is True
        assert runner.discard_pending_handoff_result(first) is False
        assert set(runner._pending_handoff_results) == {second.dispatch_id}
        assert runner._handoff_result_slots == {second.dispatch_id}
        monkeypatch.setattr(store, "append_message", append)
        runner.run("general", unrelated.objective, handoff_dispatch=unrelated)
        authorized = True
        blocked = runner.run("general", first.objective, handoff_dispatch=first)
        assert json.loads(blocked)["status"] == "blocked"
        assert len(calls) == 3
        assert len(store.list_indexed_messages(first.source_session_id)) == 1


def test_host_cannot_abandon_pending_result_during_active_retry(tmp_path, monkeypatch):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        runner = sub_agent_tool.SubAgentRunner()
        calls = []

        def run_llm(**kwargs):
            calls.append(kwargs)
            return '{"status":"completed","summary":"Stored later"}', {}, 0

        append = store.append_message

        def fail_append(*args, **kwargs):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(runner, "_run_llm", run_llm)
        monkeypatch.setattr(store, "append_message", fail_append)
        with pytest.raises(RuntimeError, match="storage unavailable"):
            runner.run("general", dispatch.objective, handoff_dispatch=dispatch)

        def append_during_retry(*args, **kwargs):
            assert runner.discard_pending_handoff_result(dispatch) is False
            assert dispatch.dispatch_id in runner._pending_handoff_results
            return append(*args, **kwargs)

        monkeypatch.setattr(store, "append_message", append_during_retry)
        result = runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert json.loads(result)["status"] == "completed"
        assert len(calls) == 1
        assert runner._pending_handoff_results == {}
        assert runner._handoff_result_slots == set()


@pytest.mark.parametrize("permission_level", ["read_only", "propose_only"])
def test_structured_dispatch_cannot_enable_live_tools(
    tmp_path, monkeypatch, permission_level
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        runner = sub_agent_tool.SubAgentRunner()
        monkeypatch.setattr(sub_agent_tool, "get_callbacks", lambda: None)
        monkeypatch.setattr(
            sub_agent_tool,
            "make_client",
            lambda callbacks: ("openai", object(), "test"),
        )
        monkeypatch.setattr(
            runner,
            "_build_tool_list_prompt",
            lambda *args: pytest.fail("structured tool discovery"),
        )
        monkeypatch.setattr(
            runner,
            "_run_llm_multi_turn",
            lambda **kwargs: pytest.fail("structured live tool execution"),
        )
        calls = []
        output = json.dumps(
            {
                "status": "completed",
                "role": "general",
                "summary": "SNAPSHOT_ONLY",
                "details": {},
                "notes": "",
            }
        )

        def call(*args, **kwargs):
            calls.append((args, kwargs))
            return output, 0, {}

        monkeypatch.setattr(runner, "_call_with_retry", call)
        result = runner.run(
            "general",
            dispatch.objective,
            handoff_dispatch=dispatch,
            permission_level=permission_level,
            completion_regex="SNAPSHOT_ONLY",
        )
        assert json.loads(result)["summary"] == "SNAPSHOT_ONLY"
        assert len(calls) == 1
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 2


def test_child_inherits_parent_identity_and_room_for_owner_cleanup(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        store.bind_identity_context(
            session_id, principal_id="owner", room_id="private-room"
        )
        dispatch = _dispatch(store, session_id, goal_id, ref)
        dispatch.record_result("PRIVATE CHILD RESULT")
        child = store.get_session(dispatch.source_session_id)
        assert child["principal_id"] == "owner"
        assert child["room_id"] == "private-room"
        assert {
            row["session_id"] for row in store.list_sessions(principal_id="owner")
        } == {session_id, dispatch.source_session_id}
        assert store.list_sessions(principal_id="other-owner") == []
        for row in store.list_sessions(principal_id="owner"):
            if row["room_id"] == "private-room":
                store.delete_session(row["session_id"])
        assert store.list_sessions() == []
        assert (
            store._connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            == 0
        )
        assert (
            store._connection.execute("SELECT COUNT(*) FROM session_items").fetchone()[
                0
            ]
            == 0
        )


def test_failed_child_identity_binding_removes_unpublished_session(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        store.bind_identity_context(
            session_id, principal_id="owner", room_id="private-room"
        )

        def fail_bind(*args, **kwargs):
            raise SessionStoreError("identity binding unavailable")

        monkeypatch.setattr(store, "bind_identity_context", fail_bind)
        with pytest.raises(SessionStoreError, match="identity binding unavailable"):
            _dispatch(store, session_id, goal_id, ref)
        assert [row["session_id"] for row in store.list_sessions()] == [session_id]


@pytest.mark.parametrize("structured", [False, True])
def test_legacy_output_contract_cannot_inject_main_text_into_snapshot(
    tmp_path, monkeypatch, structured
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref) if structured else None
        runner = sub_agent_tool.SubAgentRunner()
        monkeypatch.setattr(sub_agent_tool, "get_callbacks", lambda: None)
        monkeypatch.setattr(
            sub_agent_tool,
            "make_client",
            lambda callbacks: ("openai", object(), "test"),
        )
        prompts = []
        output = json.dumps(
            {
                "status": "completed",
                "role": "general",
                "summary": "CONTRACT_DONE",
                "details": {},
                "notes": "",
            }
        )

        def call(**kwargs):
            prompts.append(kwargs["system_prompt"])
            return output, 0, {}

        monkeypatch.setattr(runner, "_call_with_retry", call)
        original_run_llm = runner._run_llm
        worker_arguments = []

        def capture_worker_arguments(**kwargs):
            worker_arguments.append(kwargs.copy())
            return original_run_llm(**kwargs)

        monkeypatch.setattr(runner, "_run_llm", capture_worker_arguments)
        result = runner.run(
            "general",
            "Inspect regression",
            handoff_dispatch=dispatch,
            provider=("PRIVATE MAIN PROVIDER" if structured else "openai"),
            model_name=("PRIVATE MAIN MODEL" if structured else "test-model"),
            response_mode="json",
            response_schema={"description": "PRIVATE MAIN SCHEMA"},
            required_fields=["PRIVATE MAIN FIELD"],
            strict_output=False,
            evidence_required=structured,
            evidence_min_items=(
                "PRIVATE MAIN EVIDENCE MARKER" if structured else 2
            ),
            completion_regex="CONTRACT_DONE",
        )
        assert json.loads(result)["status"] == "completed"
        assert len(prompts) == 1
        assert len(worker_arguments) == 1
        if structured:
            assert worker_arguments[0]["provider"] is None
            assert worker_arguments[0]["model_name"] is None
            assert worker_arguments[0]["response_mode"] is None
            assert worker_arguments[0]["evidence_required"] is False
            assert worker_arguments[0]["evidence_min_items"] == 0
        else:
            assert worker_arguments[0]["provider"] == "openai"
            assert worker_arguments[0]["model_name"] == "test-model"
            assert worker_arguments[0]["response_mode"] == "json"
        assert ("PRIVATE MAIN SCHEMA" in prompts[0]) is (not structured)
        assert ("PRIVATE MAIN FIELD" in prompts[0]) is (not structured)


@pytest.mark.parametrize("selector", [{"when": "latest"}, {"session_id": "child"}])
def test_resume_never_queues_internal_child_session(tmp_path, monkeypatch, selector):
    from queue import Queue
    from uagent.tools import session_resume_tool

    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        dispatch.record_result("PRIVATE CHILD RESUME RESULT")
        active = store.create_session(project="test", entry_point="cli")
        store._connection.execute(
            "UPDATE sessions SET created_at='2026-10-01 00:00:00' WHERE session_id=?",
            (session_id,),
        )
        store._connection.execute(
            "UPDATE sessions SET created_at='2026-10-02 00:00:00' WHERE session_id=?",
            (dispatch.source_session_id,),
        )
        queue = Queue()
        monkeypatch.setattr(
            session_resume_tool,
            "get_callbacks",
            lambda: ToolCallbacks(
                session_store=store, session_id=active.session_id, event_queue=queue
            ),
        )
        args = dict(selector)
        if "session_id" in args:
            args["session_id"] = dispatch.source_session_id
        result = json.loads(session_resume_tool.run_tool(args))
        if "session_id" in args:
            assert result["ok"] is False
            assert queue.empty()
        else:
            assert result["session_id"] == session_id
            assert queue.get_nowait()["text"] == f":sessions load {session_id}"
        assert "PRIVATE CHILD" not in json.dumps(result)



def test_unknown_structured_role_does_not_leak_model_argument_to_logs(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id, goal_id, ref = _main(store)
        dispatch = _dispatch(store, session_id, goal_id, ref)
        monkeypatch.setattr(sub_agent_tool, "_SUB_AGENT_LOG_DIR", tmp_path / "logs")
        runner = sub_agent_tool.SubAgentRunner()
        secret_role = "PRIVATE MAIN DATA IN ROLE FIELD"
        result = runner.run(secret_role, dispatch.objective, handoff_dispatch=dispatch)
        assert secret_role not in result
        log = "\n".join(
            path.read_text() for path in (tmp_path / "logs").rglob("*.jsonl")
        )
        assert secret_role not in log
        assert '"agent_name": "structured"' in log


def test_unknown_legacy_role_keeps_existing_error_behavior(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        runner = sub_agent_tool.SubAgentRunner()
        role = "missing legacy role"
        result = runner.run(role, "ordinary legacy call")
        assert role in result
