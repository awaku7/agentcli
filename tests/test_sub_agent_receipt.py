"""Compact Sub-Agent receipts are durable, revision-checked, and unverified."""

from __future__ import annotations

import json
import threading
from dataclasses import replace

import pytest

from uagent.runtime.session_store import (
    SessionRevisionConflict,
    SessionStore,
    SessionStoreError,
)
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.runtime.sub_agent_receipt import receive_compact_sub_agent_return


def _setup(store):
    main = store.create_session(project="test", entry_point="cli")
    dispatch = _dispatch(store, main.session_id)
    dispatch.record_result(
        json.dumps({"status": "completed", "summary": "May involve caching"})
    )
    return main.session_id, dispatch


def _dispatch(store, main_id):
    return capture_sub_agent_dispatch(
        store,
        receiving_session_id=main_id,
        objective="Investigate a regression",
        task_scope="Read-only investigation",
        source_access_check=lambda _ref: False,
    )


def _receive(dispatch, *, allowed=True, role="reviewer"):
    return receive_compact_sub_agent_return(
        dispatch,
        agent_role=role,
        source_access_check=lambda _ref: allowed,
    )


def test_receiver_records_unverified_evidence_without_changing_main(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main, dispatch = _setup(store)
        before = store.get_agent_state_snapshot(main)
        receipt = _receive(dispatch)
        assert receipt == {
            "receiving_session_id": main,
            "root_handoff_id": dispatch.dispatch_id,
            "already_received": False,
        }
        assert store.get_agent_state_snapshot(main) == before
        assert len(store.list_indexed_messages(main)) == 0
        assert _receive(dispatch)["already_received"] is True
        rows = store._connection.execute(
            "SELECT record_json FROM sub_agent_receipts WHERE root_handoff_id = ?",
            (dispatch.dispatch_id,),
        ).fetchall()
        assert len(rows) == 1
        packed = json.loads(rows[0]["record_json"])
        assert packed["decisions"] == []
        assert packed["work_done"] == []
        assert "Unverified" in packed["findings"][0]["text"]


def test_receiver_rejects_stale_revision_without_durable_receipt(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main, dispatch = _setup(store)
        store.save_agent_state(main, {"memory": "newer"}, expected_revision=0)
        before = store.get_agent_state_snapshot(main)
        with pytest.raises(SessionRevisionConflict, match="older"):
            _receive(dispatch)
        assert store.get_agent_state_snapshot(main) == before
        receipt_count = store._connection.execute(
            "SELECT count(*) FROM sub_agent_receipts"
        ).fetchone()[0]
        assert receipt_count == 0


def test_receipt_retry_survives_revision_change_and_store_restart(tmp_path):
    path = tmp_path / "session.sqlite3"
    with SessionStore(path) as store:
        main, dispatch = _setup(store)
        assert _receive(dispatch)["already_received"] is False
        store.save_agent_state(main, {"memory": "later"}, expected_revision=0)
        before = store.get_agent_state_snapshot(main)
    with SessionStore(path) as reopened:
        restored = replace(dispatch, _store=reopened)
        assert _receive(restored)["already_received"] is True
        assert reopened.get_agent_state_snapshot(main) == before


def test_existing_root_cannot_be_replayed_with_another_payload(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main, dispatch = _setup(store)
        _receive(dispatch)
        before = store.get_agent_state_snapshot(main)
        from uagent.runtime.handoff_record import HandoffRecord

        row = store._connection.execute(
            "SELECT record_json FROM sub_agent_receipts"
        ).fetchone()
        saved = HandoffRecord.from_dict(json.loads(row["record_json"]))
        malicious = replace(saved, role="different-role")
        with pytest.raises(SessionStoreError, match="different receipt"):
            store.commit_sub_agent_receipt(
                malicious,
                source_session_id=dispatch.source_session_id,
                expected_role="reviewer",
                source_access_check=lambda _ref: True,
            )
        assert store.get_agent_state_snapshot(main) == before


def test_permission_revocation_and_missing_source_fail_closed(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        _main, dispatch = _setup(store)
        from uagent.runtime.compaction_record import CompactionValidationError
        from uagent.runtime.handoff_record import HandoffRecord
        from uagent.runtime.sub_agent_return import build_compact_sub_agent_return

        record = HandoffRecord.from_dict(
            json.loads(
                build_compact_sub_agent_return(
                    dispatch,
                    agent_role="reviewer",
                    source_access_check=lambda _ref: True,
                )
            )
        )
        with pytest.raises(CompactionValidationError, match="unauthorized"):
            _receive(dispatch, allowed=False)
        store._connection.execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND item_kind = 'message' "
            "AND item_id = (SELECT CAST(MAX(message_id) AS TEXT) FROM messages "
            "WHERE session_id = ?)",
            (dispatch.source_session_id, dispatch.source_session_id),
        )
        with pytest.raises(CompactionValidationError, match="missing or ambiguous"):
            _receive(dispatch)
        with pytest.raises(SessionStoreError, match="unavailable"):
            store.commit_sub_agent_receipt(
                record,
                source_session_id=dispatch.source_session_id,
                expected_role="reviewer",
                source_access_check=lambda _ref: True,
            )
        receipt_count = store._connection.execute(
            "SELECT count(*) FROM sub_agent_receipts"
        ).fetchone()[0]
        assert receipt_count == 0


def test_second_session_does_not_inherit_child_result(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        _main, dispatch = _setup(store)
        other = store.create_session(project="other", entry_point="cli")
        from uagent.runtime.handoff_record import HandoffRecord

        from uagent.runtime.sub_agent_return import build_compact_sub_agent_return

        record = HandoffRecord.from_dict(
            json.loads(
                build_compact_sub_agent_return(
                    dispatch,
                    agent_role="reviewer",
                    source_access_check=lambda _ref: True,
                )
            )
        )
        forged = replace(
            record,
            receiving_session_id=other.session_id,
        )
        with pytest.raises(SessionStoreError, match="scope mismatch"):
            store.commit_sub_agent_receipt(
                forged,
                source_session_id=dispatch.source_session_id,
                expected_role="reviewer",
                source_access_check=lambda _ref: True,
            )


def test_two_receivers_commit_one_root_across_connections(tmp_path):
    path = tmp_path / "session.sqlite3"
    with SessionStore(path) as primary, SessionStore(path) as secondary:
        _main, dispatch = _setup(primary)
        barrier = threading.Barrier(2)
        receipts = []
        errors = []

        def submit(store):
            try:
                other = replace(dispatch, _store=store)
                barrier.wait(timeout=3)
                receipts.append(_receive(other))
            except Exception as exc:
                errors.append(exc)

        a = threading.Thread(target=submit, args=(primary,))
        b = threading.Thread(target=submit, args=(secondary,))
        a.start()
        b.start()
        a.join(8)
        b.join(8)
        assert not a.is_alive() and not b.is_alive()
        assert errors == []
        assert sorted(item["already_received"] for item in receipts) == [
            False,
            True,
        ]
        receipt_count = primary._connection.execute(
            "SELECT count(*) FROM sub_agent_receipts"
        ).fetchone()[0]
        assert receipt_count == 1


@pytest.mark.parametrize(
    "field", ["finding", "objective", "goal_ids", "agent_id", "role"]
)
def test_first_receipt_must_match_indexed_dispatch_and_output(tmp_path, field):
    from uagent.runtime.handoff_record import HandoffRecord
    from uagent.runtime.sub_agent_return import build_compact_sub_agent_return

    with SessionStore(tmp_path / "session.sqlite3") as store:
        main, dispatch = _setup(store)
        legitimate = HandoffRecord.from_dict(
            json.loads(
                build_compact_sub_agent_return(
                    dispatch,
                    agent_role="reviewer",
                    source_access_check=lambda _ref: True,
                )
            )
        )
        if field == "finding":
            injected = replace(
                legitimate,
                findings=(
                    replace(
                        legitimate.findings[0],
                        text="Unverified Sub-Agent report (completed): invented",
                    ),
                ),
            )
        elif field == "objective":
            injected = replace(legitimate, objective="Invented task")
        elif field == "goal_ids":
            injected = replace(legitimate, goal_ids=("invented-goal",))
        elif field == "agent_id":
            injected = replace(legitimate, agent_id="fake-agent")
        else:
            injected = replace(legitimate, role="attacker")
        with pytest.raises(SessionStoreError, match="does not match"):
            store.commit_sub_agent_receipt(
                injected,
                source_session_id=dispatch.source_session_id,
                expected_role="reviewer",
                source_access_check=lambda _ref: True,
            )
        assert store.get_agent_state_snapshot(main) == (None, 0)
        receipt_count = store._connection.execute(
            "SELECT count(*) FROM sub_agent_receipts"
        ).fetchone()[0]
        assert receipt_count == 0
        assert _receive(dispatch)["already_received"] is False


def test_redacted_dispatch_scope_stays_parseable_for_secret_objective(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main = store.create_session(project="test", entry_point="cli")
        dispatch = capture_sub_agent_dispatch(
            store,
            receiving_session_id=main.session_id,
            objective="Investigate api_key=secret",
            task_scope="Read-only investigation",
            source_access_check=lambda _ref: False,
        )
        dispatch.record_result(
            '{"status":"completed","summary":"Investigated the bug"}'
        )
        scope = store.list_indexed_messages(dispatch.source_session_id)[0]["payload"][
            "dispatch_scope"
        ]
        assert "secret" not in json.dumps(scope)
        assert scope["objective"].startswith("Investigate api_key=")
        assert _receive(dispatch)["already_received"] is False
        saved = store._connection.execute(
            "SELECT record_json FROM sub_agent_receipts"
        ).fetchone()["record_json"]
        assert "secret" not in saved


def test_receipt_survives_child_cleanup_and_remains_idempotent(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main, dispatch = _setup(store)
        _receive(dispatch)
        row = store._connection.execute(
            "SELECT record_json FROM sub_agent_receipts WHERE root_handoff_id = ?",
            (dispatch.dispatch_id,),
        ).fetchone()
        from uagent.runtime.handoff_record import HandoffRecord

        record = HandoffRecord.from_dict(json.loads(row["record_json"]))
        store.delete_session(dispatch.source_session_id)
        present = store._connection.execute(
            "SELECT count(*) FROM sub_agent_receipts WHERE root_handoff_id = ?",
            (dispatch.dispatch_id,),
        ).fetchone()[0]
        assert present == 1
        replayed = store.commit_sub_agent_receipt(
            record,
            source_session_id=dispatch.source_session_id,
            expected_role="reviewer",
            source_access_check=lambda _ref: True,
        )
        assert replayed["already_received"] is True
        store.delete_session(main)
        removed = store._connection.execute(
            "SELECT count(*) FROM sub_agent_receipts"
        ).fetchone()[0]
        assert removed == 0
