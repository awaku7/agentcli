from __future__ import annotations

import json

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

        def revoke(*args):
            nonlocal allowed
            allowed = False
            return True

        monkeypatch.setattr(runner.duplicate_guard, "check_and_record", revoke)
        monkeypatch.setattr(
            runner, "_run_llm", lambda **kwargs: pytest.fail("must not call provider")
        )
        with pytest.raises(CompactionValidationError, match="delivery"):
            runner.run("general", dispatch.objective, handoff_dispatch=dispatch)
        assert len(store.list_indexed_messages(dispatch.source_session_id)) == 1
