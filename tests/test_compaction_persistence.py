from __future__ import annotations

import pytest

from uagent.runtime.compaction_record import (
    CompactionRecord,
    ConstraintRecord,
    DecisionRecord,
    GoalDelta,
    ProvenancedObservation,
    SourceRef,
)
from uagent.runtime.session_store import (
    SessionComparisonUnavailable,
    SessionRevisionConflict,
    SessionStore,
    SessionStoreError,
)


def _source(session_id: str, seq: int = 1) -> SourceRef:
    return SourceRef(
        kind="message",
        ref_id=str(seq),
        scope_id=session_id,
        session_seq=seq,
    )


def _goal_delta(session_id: str, *, delta_id: str = "delta-1") -> GoalDelta:
    source = _source(session_id)
    return GoalDelta(
        goal_delta_id=delta_id,
        association="new",
        title_hint="Ship structured checkpoints",
        status_observations=(
            ProvenancedObservation(text="in_progress", source_refs=(source,)),
        ),
        progress_events=(
            ProvenancedObservation(
                text="record model and reducer are implemented", source_refs=(source,)
            ),
        ),
        source_refs=(source,),
    )


def _record(
    session_id: str,
    *,
    operation_id: str = "operation-1",
    application_status: str = "applied",
    base_revision: int = 0,
    goal_deltas: tuple[GoalDelta, ...] | None = None,
    committed_revision: int | None = None,
) -> CompactionRecord:
    return CompactionRecord(
        record_id=f"checkpoint-{operation_id}",
        operation_id=operation_id,
        application_status=application_status,
        session_id=session_id,
        actor_kind="runtime",
        actor_id="test-runtime",
        source_start_seq=1,
        source_end_seq=1,
        base_revision=base_revision,
        committed_revision=committed_revision,
        goal_deltas=(
            goal_deltas if goal_deltas is not None else (_goal_delta(session_id),)
        ),
    )


def _session(store: SessionStore) -> str:
    session = store.create_session(project="compaction", entry_point="test")
    store.append_message(session.session_id, "user", "implement compaction")
    return session.session_id


def test_applied_checkpoint_and_agent_state_commit_atomically_and_idempotently(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        record = _record(session_id)

        committed = store.commit_compaction_record(record)
        state = store.get_agent_state(session_id)
        retried = store.commit_compaction_record(record)

        assert committed["result_revision"] == 1
        assert committed["record"]["committed_revision"] == 1
        assert store.get_agent_state_revision(session_id) == 1
        structured = state["structured_compaction"]
        assert len(structured["goals"]) == 1
        goal = next(iter(structured["goals"].values()))
        assert goal["title"] == "Ship structured checkpoints"
        assert goal["progress_events"][0]["text"].startswith("record model")
        assert structured["applied_operations"] == ["operation-1"]
        assert store.get_session_item_watermark(session_id) == 2
        checkpoint_items = store.list_session_items(session_id, start_seq=2, end_seq=2)
        assert checkpoint_items[0]["item_kind"] == "checkpoint"
        assert checkpoint_items[0]["item_id"] == "checkpoint-operation-1"
        assert retried["already_committed"] is True
        assert store.get_agent_state_revision(session_id) == 1
        assert store.get_compaction_record("operation-1")["result_revision"] == 1


def test_revision_conflict_does_not_create_checkpoint_or_change_state(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        store.save_agent_state(session_id, {"goal": "unrelated update"})
        before = store.get_agent_state(session_id)

        with pytest.raises(
            SessionRevisionConflict, match="expected AgentState revision 0"
        ):
            store.commit_compaction_record(_record(session_id, base_revision=0))

        assert store.get_compaction_record("operation-1") is None
        assert store.get_agent_state(session_id) == before
        assert store.get_agent_state_revision(session_id) == 1


def test_reducer_failure_rolls_back_checkpoint_row(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        source = _source(session_id)
        bad_delta = GoalDelta(
            goal_delta_id="delta-bad",
            association="new",
            title_hint="Invalid decision lineage",
            decisions=(
                DecisionRecord(
                    decision_id="decision-new",
                    decision="use the stable design",
                    supersedes=("missing-decision",),
                    source_refs=(source,),
                ),
            ),
            source_refs=(source,),
        )

        with pytest.raises(SessionStoreError, match="cannot supersede unknown"):
            store.commit_compaction_record(
                _record(session_id, goal_deltas=(bad_delta,))
            )

        assert store.get_compaction_record("operation-1") is None
        assert store.get_agent_state(session_id) is None
        assert store.get_agent_state_revision(session_id) == 0


def test_sql_failure_after_checkpoint_insert_rolls_back_both_rows(
    tmp_path, monkeypatch
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        original_execute = store._execute

        def fail_state_update(sql: str, parameters=()):
            if sql.lstrip().startswith("INSERT INTO agent_states"):
                raise SessionStoreError("injected state write failure")
            return original_execute(sql, parameters)

        monkeypatch.setattr(store, "_execute", fail_state_update)
        with pytest.raises(SessionStoreError, match="injected state write failure"):
            store.commit_compaction_record(_record(session_id))

        monkeypatch.setattr(store, "_execute", original_execute)
        assert store.get_compaction_record("operation-1") is None
        assert store.get_agent_state(session_id) is None
        assert store.get_agent_state_revision(session_id) == 0
        assert store.get_session_item_watermark(session_id) == 1


def test_comparison_only_persists_record_without_reducing_or_advancing_revision(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        store.save_agent_state(session_id, {"goal": "existing state"})
        before = store.get_agent_state(session_id)
        revision = store.get_agent_state_revision(session_id)
        record = _record(
            session_id,
            operation_id="comparison-1",
            application_status="comparison_only",
            base_revision=revision,
        )

        result = store.commit_compaction_record(record)

        assert result["result_revision"] is None
        assert result["record"]["committed_revision"] is None
        assert store.get_agent_state(session_id) == before
        assert store.get_agent_state_revision(session_id) == revision
        assert (
            store.get_compaction_record("comparison-1")["application_status"]
            == "comparison_only"
        )


def test_comparison_only_requires_available_matching_snapshot(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        with pytest.raises(
            SessionComparisonUnavailable,
            match="no saved AgentState snapshot",
        ):
            store.commit_compaction_record(
                _record(
                    session_id,
                    operation_id="comparison-1",
                    application_status="comparison_only",
                    base_revision=0,
                )
            )
        assert store.get_compaction_record("comparison-1") is None
        assert store.get_agent_state(session_id) is None
        assert store.get_agent_state_revision(session_id) == 0


def test_comparison_only_past_revision_is_unavailable_not_head_conflict(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        store.commit_compaction_record(_record(session_id))
        store.save_agent_state(session_id, {"goal": "advanced state"})
        before_state, before_revision = store.get_agent_state_snapshot(session_id)

        with pytest.raises(
            SessionComparisonUnavailable,
            match="historical AgentState snapshot for base revision 1 is not retained",
        ):
            store.commit_compaction_record(
                _record(
                    session_id,
                    operation_id="historical-comparison",
                    application_status="comparison_only",
                    base_revision=1,
                )
            )

        assert store.get_compaction_record("historical-comparison") is None
        assert store.get_agent_state_snapshot(session_id) == (
            before_state,
            before_revision,
        )


def test_agent_state_stale_writer_is_rejected_when_revision_is_supplied(
    tmp_path,
) -> None:
    db_path = tmp_path / "sessions.sqlite3"
    with SessionStore(db_path) as first_client, SessionStore(db_path) as second_client:
        session_id = _session(first_client)
        first_client.save_agent_state(session_id, {"goal": "initial"})
        first_state, first_revision = first_client.get_agent_state_snapshot(session_id)
        second_state, second_revision = second_client.get_agent_state_snapshot(
            session_id
        )
        assert first_state == second_state == {"goal": "initial"}
        assert first_revision == second_revision == 1

        first_client.save_agent_state(
            session_id,
            {"goal": "first writer"},
            expected_revision=first_revision,
        )
        with pytest.raises(
            SessionRevisionConflict, match="expected AgentState revision 1"
        ):
            second_client.save_agent_state(
                session_id,
                {"goal": "stale second writer"},
                expected_revision=second_revision,
            )

        assert first_client.get_agent_state(session_id) == {"goal": "first writer"}
        assert first_client.get_agent_state_revision(session_id) == 2


def test_ambiguous_delta_is_preserved_unresolved_until_authorized(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        source = _source(session_id)
        ambiguous = GoalDelta(
            goal_delta_id="ambiguous-1",
            association="ambiguous",
            candidate_goal_ids=(),
            title_hint="Possibly a separate workstream",
            progress_events=(
                ProvenancedObservation(text="maybe done", source_refs=(source,)),
            ),
            source_refs=(source,),
        )
        store.commit_compaction_record(_record(session_id, goal_deltas=(ambiguous,)))
        state = store.get_agent_state(session_id)["structured_compaction"]
        assert state["goals"] == {}
        unresolved = next(iter(state["unresolved_goal_deltas"].values()))
        assert unresolved["resolution_status"] == "unresolved"
        assert unresolved["goal_delta"]["progress_events"][0]["text"] == "maybe done"

        resolution = GoalDelta(
            goal_delta_id="resolution-1",
            association="new",
            title_hint="Confirmed workstream",
            resolves_ambiguous_delta_ids=("ambiguous-1",),
            progress_events=(
                ProvenancedObservation(
                    text="confirmed progress", source_refs=(source,)
                ),
            ),
            source_refs=(source,),
        )
        with pytest.raises(
            SessionStoreError, match="lacks explicit runtime authorization"
        ):
            store.commit_compaction_record(
                _record(
                    session_id,
                    operation_id="resolution-1",
                    base_revision=1,
                    goal_deltas=(resolution,),
                )
            )
        assert store.get_agent_state_revision(session_id) == 1
        assert store.get_compaction_record("resolution-1") is None

        store.commit_compaction_record(
            _record(
                session_id,
                operation_id="resolution-1",
                base_revision=1,
                goal_deltas=(resolution,),
            ),
            authorized_resolution_ids=("ambiguous-1",),
        )
        state = store.get_agent_state(session_id)["structured_compaction"]
        unresolved = next(iter(state["unresolved_goal_deltas"].values()))
        assert unresolved["resolution_status"] == "resolved"
        assert len(state["goals"]) == 1
        goal_id = unresolved["resolved_by"]["goal_id"]
        goal = state["goals"][goal_id]
        assert [event["text"] for event in goal["progress_events"]] == [
            "maybe done",
            "confirmed progress",
        ]
        assert state["goal_delta_assignments"]["operation-1:ambiguous-1"] == goal_id


def test_legacy_agent_state_save_preserves_reducer_namespace(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        store.commit_compaction_record(_record(session_id))
        structured_before = store.get_agent_state(session_id)["structured_compaction"]

        store.save_agent_state(
            session_id,
            {
                "goal": "legacy progress update",
                "structured_compaction": {"schema_version": 999, "goals": {}},
            },
        )

        state = store.get_agent_state(session_id)
        assert state["goal"] == "legacy progress update"
        assert state["structured_compaction"] == structured_before
        assert store.get_agent_state_revision(session_id) == 2


def test_retry_is_idempotent_after_source_prune_and_later_state_update(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        record = _record(session_id)
        first = store.commit_compaction_record(record)
        store._execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND session_seq = 1",
            (session_id,),
        )
        store.save_agent_state(session_id, {"goal": "later state"})

        retry = store.commit_compaction_record(record)

        assert first["result_revision"] == 1
        assert retry["already_committed"] is True
        assert store.get_agent_state_revision(session_id) == 2
        assert store.get_agent_state(session_id)["goal"] == "later state"


def test_record_json_is_parseable_and_revision_metadata_is_not_in_state_payload(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        result = store.commit_compaction_record(_record(session_id))
        stored = store.get_compaction_record("operation-1")
        assert stored["record"]["committed_revision"] == 1
        assert result["record"] == stored["record"]
        assert "revision" not in store.get_agent_state(session_id)


def test_invalid_session_source_reference_is_rejected(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        invalid_source = SourceRef(
            kind="message",
            ref_id="not-message-1",
            scope_id=session_id,
            session_seq=1,
        )
        delta = GoalDelta(
            goal_delta_id="bad-provenance",
            association="new",
            title_hint="Reject forged source ID",
            status_observations=(
                ProvenancedObservation(text="done", source_refs=(invalid_source,)),
            ),
            source_refs=(invalid_source,),
        )

        with pytest.raises(SessionStoreError, match="does not resolve"):
            store.commit_compaction_record(_record(session_id, goal_deltas=(delta,)))

        assert store.get_compaction_record("operation-1") is None
        assert store.get_agent_state(session_id) is None


def test_legacy_agent_state_table_is_migrated_with_revision_zero(tmp_path) -> None:
    import sqlite3

    db_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            project_key TEXT NOT NULL,
            project_path TEXT,
            entry_point TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            principal_id TEXT,
            room_id TEXT
        );
        CREATE TABLE agent_states (
            session_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO sessions(session_id, project_key, entry_point)
        VALUES ('legacy-session', 'legacy', 'test');
        INSERT INTO agent_states(session_id, state_json, updated_at)
        VALUES ('legacy-session', '{"goal":"legacy"}', '2026-01-01T00:00:00+00:00');
        """)
    connection.commit()
    connection.close()

    with SessionStore(db_path) as store:
        assert store.get_agent_state("legacy-session") == {"goal": "legacy"}
        assert store.get_agent_state_revision("legacy-session") == 0
        store.save_agent_state("legacy-session", {"goal": "updated"})
        assert store.get_agent_state_revision("legacy-session") == 1
        columns = {
            row["name"] for row in store._execute("PRAGMA table_info(agent_states)")
        }

    assert {"revision", "updated_by_client"}.issubset(columns)


def test_reducer_preserves_decision_and_constraint_revert_lineage(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        source = _source(session_id)
        initial_delta = GoalDelta(
            goal_delta_id="initial-goal",
            association="new",
            title_hint="Track reversible decisions",
            decisions=(
                DecisionRecord(
                    decision_id="decision-1",
                    decision="keep the old policy",
                    source_refs=(source,),
                ),
            ),
            constraints=(
                ConstraintRecord(
                    constraint_id="constraint-1",
                    constraint="do not overwrite raw history",
                    source_refs=(source,),
                ),
            ),
            source_refs=(source,),
        )
        store.commit_compaction_record(
            _record(session_id, goal_deltas=(initial_delta,))
        )
        goal_id = next(
            iter(store.get_agent_state(session_id)["structured_compaction"]["goals"])
        )
        revised_delta = GoalDelta(
            goal_delta_id="revert-goal",
            association="existing",
            goal_id=goal_id,
            decisions=(
                DecisionRecord(
                    decision_id="decision-2",
                    decision="revert the old policy",
                    status="reverted",
                    supersedes=("decision-1",),
                    source_refs=(source,),
                ),
            ),
            constraints=(
                ConstraintRecord(
                    constraint_id="constraint-2",
                    constraint="revoke the previous constraint",
                    status="revoked",
                    supersedes=("constraint-1",),
                    source_refs=(source,),
                ),
            ),
            source_refs=(source,),
        )

        store.commit_compaction_record(
            _record(
                session_id,
                operation_id="operation-2",
                base_revision=1,
                goal_deltas=(revised_delta,),
            )
        )

        goal = store.get_agent_state(session_id)["structured_compaction"]["goals"][
            goal_id
        ]
        assert goal["decisions"]["decision-1"]["status"] == "reverted"
        assert goal["decisions"]["decision-2"]["status"] == "reverted"
        assert goal["constraints"]["constraint-1"]["status"] == "revoked"
        assert goal["constraints"]["constraint-2"]["status"] == "revoked"


def test_legacy_agent_state_save_can_use_expected_revision_guard(tmp_path) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        store.save_agent_state(session_id, {"goal": "initial"}, expected_revision=0)
        before = store.get_agent_state(session_id)

        with pytest.raises(
            SessionRevisionConflict, match="expected AgentState revision 0"
        ):
            store.save_agent_state(
                session_id, {"goal": "stale overwrite"}, expected_revision=0
            )

        assert store.get_agent_state(session_id) == before
        assert store.get_agent_state_revision(session_id) == 1


def test_reducer_rejects_duplicate_new_goal_title_without_splitting_state(
    tmp_path,
) -> None:
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        session_id = _session(store)
        store.commit_compaction_record(_record(session_id))
        before = store.get_agent_state(session_id)
        duplicate = GoalDelta(
            goal_delta_id="duplicate-title",
            association="new",
            title_hint="SHIP STRUCTURED CHECKPOINTS",
            source_refs=(_source(session_id),),
        )

        with pytest.raises(SessionStoreError, match="duplicates an existing title"):
            store.commit_compaction_record(
                _record(
                    session_id,
                    operation_id="operation-2",
                    base_revision=1,
                    goal_deltas=(duplicate,),
                )
            )

        assert store.get_agent_state(session_id) == before
        assert store.get_agent_state_revision(session_id) == 1
        assert store.get_compaction_record("operation-2") is None
