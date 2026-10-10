"""CLI opt-in and exact Goal/source grants for structured Sub-Agent Jobs."""

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
from uagent.runtime.sub_agent_host_policy import (
    build_scoped_job_handoff_policy,
    cli_scoped_handoff_policy_from_environment,
)
from uagent.runtime.sub_agent_jobs import (
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
)


def _main(store):
    main = store.create_session(project="test", entry_point="cli")
    store.append_message(main.session_id, "user", "PRIVATE MESSAGE")
    indexed = store.list_indexed_messages(main.session_id)[0]
    ref = SourceRef(
        "message", indexed["ref_id"], main.session_id, indexed["session_seq"]
    )
    owner = SubAgentJobOwner(entry_point="cli", session_id=main.session_id)
    return owner, ref


def _save_goal(store, owner, ref):
    store.commit_compaction_record(
        CompactionRecord(
            record_id="checkpoint",
            operation_id="operation",
            application_status="applied",
            session_id=owner.session_id,
            actor_kind="runtime",
            actor_id="test",
            source_start_seq=1,
            source_end_seq=1,
            base_revision=0,
            goal_deltas=(
                GoalDelta(
                    goal_delta_id="d1",
                    association="new",
                    title_hint="Investigate incident",
                    progress_events=(
                        ProvenancedObservation("Investigating", (ref,)),
                    ),
                    source_refs=(ref,),
                ),
                GoalDelta(
                    goal_delta_id="d2",
                    association="new",
                    title_hint="Unrelated confidential goal",
                    source_refs=(ref,),
                ),
            ),
        )
    )
    goals = store.get_agent_state(owner.session_id)["structured_compaction"][
        "goals"
    ]
    return next(
        goal_id
        for goal_id, goal in goals.items()
        if goal["title"] == "Investigate incident"
    )

def _settings():
    return SubAgentJobSettings(
        workers=1,
        queue_limit=4,
        owner_limit=4,
        completed_limit=8,
        result_ttl_sec=60,
        event_limit=10,
        log_max_bytes=4096,
        result_max_bytes=4096,
        shutdown_timeout_sec=0.2,
    )


def test_cli_default_remains_legacy_and_explicit_empty_grants_are_bounded(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, _ref = _main(store)
        assert cli_scoped_handoff_policy_from_environment(store, {}) is None
        policy = cli_scoped_handoff_policy_from_environment(
            store, {"UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1"}
        )
        assert policy is not None
        dispatch = policy(owner, "reviewer", "Inspect issue")
        projected = json.loads(dispatch.render_context())
        assert projected["objective"] == "Inspect issue"
        assert projected["goals"] == []
        assert projected["receiving_session_id"] == owner.session_id
        assert "PRIVATE MESSAGE" not in dispatch.render_context()


def test_explicit_goal_and_indexed_source_grants_do_not_leak_unselected_goals(
    tmp_path,
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, ref = _main(store)
        goal_id = _save_goal(store, owner, ref)
        policy = cli_scoped_handoff_policy_from_environment(
            store,
            {
                "UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "true",
                "UAGENT_SUB_AGENT_HANDOFF_GOAL_IDS": json.dumps([goal_id]),
                "UAGENT_SUB_AGENT_HANDOFF_SOURCE_REFS": json.dumps(
                    [ref.to_dict()]
                ),
            },
        )
        dispatch = policy(owner, "reviewer", "Investigate incident")
        projected = json.loads(dispatch.render_context())
        assert [item["goal_id"] for item in projected["goals"]] == [goal_id]
        assert projected["goals"][0]["status_observations"][0]["text"] == "Investigating"
        assert "Unrelated confidential goal" not in dispatch.render_context()
        assert "PRIVATE MESSAGE" not in dispatch.render_context()
        assert dispatch.bounds.source_refs == (ref,)
        assert dispatch.bounds.receiving_base_revision == 1


def test_revoked_or_resequenced_parent_source_is_rejected(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, ref = _main(store)
        policy = build_scoped_job_handoff_policy(
            store, entry_point="cli", source_refs=(ref,)
        )
        dispatch = policy(owner, "reviewer", "Inspect")
        store._connection.execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND item_kind = 'message'",
            (owner.session_id,),
        )
        with pytest.raises(CompactionValidationError, match="delivery"):
            dispatch.render_context()
        with pytest.raises(CompactionValidationError, match="unavailable"):
            policy(owner, "reviewer", "Inspect again")


def test_other_owner_session_and_entry_point_cannot_reuse_grants(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, ref = _main(store)
        other = store.create_session(project="test", entry_point="cli")
        policy = build_scoped_job_handoff_policy(
            store, entry_point="cli", source_refs=(ref,)
        )
        other_owner = SubAgentJobOwner(entry_point="cli", session_id=other.session_id)
        with pytest.raises(CompactionValidationError, match="another Session"):
            policy(other_owner, "reviewer", "Inspect")
        wrong_host = SubAgentJobOwner(
            entry_point="web", session_id=owner.session_id
        )
        with pytest.raises(CompactionValidationError, match="entry point"):
            policy(wrong_host, "reviewer", "Inspect")


def test_missing_goal_rejected_before_child_session_is_published(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, _ref = _main(store)
        policy = build_scoped_job_handoff_policy(
            store, entry_point="cli", goal_ids=("missing",)
        )
        before = len(store.list_sessions())
        with pytest.raises(CompactionValidationError, match="schema"):
            policy(owner, "reviewer", "Inspect")
        assert len(store.list_sessions()) == before


@pytest.mark.parametrize(
    "config",
    [
        {"UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "perhaps"},
        {
            "UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1",
            "UAGENT_SUB_AGENT_HANDOFF_GOAL_IDS": '{"g1":true}',
        },
        {
            "UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1",
            "UAGENT_SUB_AGENT_HANDOFF_GOAL_IDS": '["g1", "g1"]',
        },
        {
            "UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1",
            "UAGENT_SUB_AGENT_HANDOFF_SOURCE_REFS": '[{"kind":"artifact"}]',
        },
        {
            "UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1",
            "UAGENT_SUB_AGENT_HANDOFF_SOURCE_REFS": '[{"kind":"message"}]',
        },
    ],
)
def test_invalid_cli_opt_in_configuration_fails_closed(tmp_path, config):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        with pytest.raises((ValueError, CompactionValidationError)):
            cli_scoped_handoff_policy_from_environment(store, config)


def test_opt_in_requires_store(tmp_path):
    with pytest.raises(ValueError, match="SessionStore"):
        cli_scoped_handoff_policy_from_environment(
            None, {"UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1"}
        )


def test_manager_accepts_only_host_selected_dispatch(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, _ref = _main(store)
        policy = build_scoped_job_handoff_policy(store, entry_point="cli")
        manager = SubAgentJobManager(
            _settings(), handoff_dispatch_policy=policy
        )
        try:
            def worker(context):
                context.record_handoff_result(
                    context.handoff_dispatch,
                    '{"status":"completed","summary":"Investigated"}',
                )
                return '{"status":"completed","summary":"Investigated"}'

            accepted = manager.spawn(
                owner=owner,
                agent_name="reviewer",
                task="Investigate safely",
                worker=worker,
            )
            assert accepted["status"] == "accepted"
            result = manager.wait(
                owner=owner, job_id=accepted["job_id"], timeout=2
            )
            assert result["state"] == "completed"
            indexed = store.list_indexed_messages(owner.session_id)
            assert len(indexed) == 1
            assert store.get_agent_state_snapshot(owner.session_id) == (None, 0)
        finally:
            manager.shutdown()
