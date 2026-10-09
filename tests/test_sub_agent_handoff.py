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
from uagent.runtime.session_store import SessionStore
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
