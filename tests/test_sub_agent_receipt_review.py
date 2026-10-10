"""Auditable Sub-Agent receipt reviews never apply Main AgentState."""

from __future__ import annotations

import json
import threading

import pytest

from uagent.runtime.compaction_record import SourceRef
from uagent.runtime.session_store import (
    SessionRevisionConflict,
    SessionStore,
    SessionStoreError,
)
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.runtime.sub_agent_receipt import receive_compact_sub_agent_return
from uagent.runtime.sub_agent_receipt_context import format_sub_agent_receipt_context


def _setup(store):
    main = store.create_session(project="test", entry_point="cli")
    main_id = main.session_id
    store.append_message(
        main_id, "user", "Independent human review evidence for the report"
    )
    indexed = store.list_indexed_messages(main_id)[0]
    evidence = SourceRef("message", indexed["ref_id"], main_id, indexed["session_seq"])
    dispatch = capture_sub_agent_dispatch(
        store,
        receiving_session_id=main_id,
        objective="Investigate the issue",
        task_scope="Read-only",
        source_access_check=lambda _ref: False,
    )
    dispatch.record_result(
        json.dumps({"status": "completed", "summary": "Needs confirmation"})
    )
    receive_compact_sub_agent_return(
        dispatch, agent_role="reviewer", source_access_check=lambda _ref: True
    )
    return main_id, dispatch, evidence


def _review(store, main_id, dispatch, evidence, **changes):
    kwargs = {
        "reviewer_id": "operator:local",
        "outcome": "supported",
        "evidence_refs": (evidence,),
        "expected_revision": 0,
        "source_access_check": lambda _ref: True,
    }
    kwargs.update(changes)
    return store.review_sub_agent_receipt(main_id, dispatch.dispatch_id, **kwargs)


def _count(store):
    return store._connection.execute(
        "SELECT count(*) FROM sub_agent_receipt_reviews"
    ).fetchone()[0]


def test_review_is_separate_from_main_state_goal_and_receipt(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        before = store.get_agent_state_snapshot(main)
        first = _review(store, main, dispatch, evidence)
        assert first == {
            "root_handoff_id": dispatch.dispatch_id,
            "outcome": "supported",
            "already_reviewed": False,
        }
        review = store.get_sub_agent_receipt_review(main, dispatch.dispatch_id)
        assert review["reviewer_id"] == "operator:local"
        assert review["outcome"] == "supported"
        assert review["evidence_available"] is True
        assert review["evidence_refs"] == [evidence.to_dict()]
        assert store.get_agent_state_snapshot(main) == before
        assert store.list_visible_sub_agent_receipts(main)[0]["root_handoff_id"] == (
            dispatch.dispatch_id
        )
        assert _count(store) == 1


def test_identical_replay_survives_revision_and_process_restart(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path) as store:
        main, dispatch, evidence = _setup(store)
        assert _review(store, main, dispatch, evidence)["already_reviewed"] is False
        store.save_agent_state(main, {"memory": "updated"}, expected_revision=0)
        before = store.get_agent_state_snapshot(main)
    with SessionStore(path) as reopened:
        assert _review(reopened, main, dispatch, evidence)["already_reviewed"] is True
        assert reopened.get_agent_state_snapshot(main) == before
        assert _count(reopened) == 1


def test_conflicting_replays_and_other_main_sessions_are_rejected(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        other = store.create_session(project="test", entry_point="cli")
        assert (
            store.get_sub_agent_receipt_review(other.session_id, dispatch.dispatch_id)
            is None
        )
        with pytest.raises(SessionStoreError, match="not owned"):
            _review(store, other.session_id, dispatch, evidence)
        _review(store, main, dispatch, evidence)
        with pytest.raises(SessionStoreError, match="different recorded review"):
            _review(store, main, dispatch, evidence, outcome="rejected")
        assert _count(store) == 1


def test_missing_receipt_or_stale_main_revision_cannot_be_reviewed(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        with pytest.raises(SessionStoreError, match="not owned"):
            store.review_sub_agent_receipt(
                main,
                "missing-root",
                reviewer_id="operator:local",
                outcome="supported",
                evidence_refs=(evidence,),
                expected_revision=0,
                source_access_check=lambda _ref: True,
            )
        store.save_agent_state(main, {"memory": "new"}, expected_revision=0)
        with pytest.raises(SessionRevisionConflict, match="revision"):
            _review(store, main, dispatch, evidence)
        assert _count(store) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "complete"},
        {"reviewer_id": ""},
        {"evidence_refs": ()},
        {"expected_revision": -1},
        {"source_access_check": None},
    ],
)
def test_invalid_host_review_inputs_fail_closed(tmp_path, changes):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        with pytest.raises((ValueError, TypeError)):
            _review(store, main, dispatch, evidence, **changes)
        assert _count(store) == 0


def test_review_evidence_must_be_independent_current_user_message(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        output = next(
            item
            for item in store.list_indexed_messages(dispatch.source_session_id)
            if item["role"] == "assistant"
        )
        child = SourceRef(
            "message",
            output["ref_id"],
            dispatch.source_session_id,
            output["session_seq"],
        )
        with pytest.raises(SessionStoreError, match="unavailable or unauthorized"):
            _review(store, main, dispatch, evidence, evidence_refs=(child,))
        store.append_message(main, "assistant", "Untrusted model affirmation")
        model_output = store.list_indexed_messages(main)[-1]
        model_ref = SourceRef(
            "message", model_output["ref_id"], main, model_output["session_seq"]
        )
        with pytest.raises(SessionStoreError, match="separate Main user message"):
            _review(store, main, dispatch, evidence, evidence_refs=(model_ref,))
        with pytest.raises(SessionStoreError, match="unavailable or unauthorized"):
            _review(
                store,
                main,
                dispatch,
                evidence,
                source_access_check=lambda _ref: False,
            )
        store._connection.execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND item_kind = 'message' AND item_id = ?",
            (main, evidence.ref_id),
        )
        with pytest.raises(SessionStoreError, match="unavailable or unauthorized"):
            _review(store, main, dispatch, evidence)
        assert _count(store) == 0


def test_missing_child_output_prevents_new_review(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        store.delete_session(dispatch.source_session_id)
        with pytest.raises(SessionStoreError, match="no longer available"):
            _review(store, main, dispatch, evidence)
        assert _count(store) == 0


def test_rejection_is_audit_only_and_review_survives_child_cleanup(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        before = store.get_agent_state_snapshot(main)
        _review(store, main, dispatch, evidence, outcome="rejected")
        store.delete_session(dispatch.source_session_id)
        assert store.get_sub_agent_receipt_review(main, dispatch.dispatch_id)[
            "outcome"
        ] == ("rejected")
        assert store.get_agent_state_snapshot(main) == before
        store._connection.execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND item_kind = 'message' AND item_id = ?",
            (main, evidence.ref_id),
        )
        assert (
            store.get_sub_agent_receipt_review(main, dispatch.dispatch_id)[
                "evidence_available"
            ]
            is False
        )
        store.delete_session(main)
        assert _count(store) == 0


def test_concurrent_reviewers_cannot_store_two_decisions(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path) as first, SessionStore(path) as second:
        main, dispatch, evidence = _setup(first)
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def submit(store):
            try:
                barrier.wait(timeout=3)
                results.append(_review(store, main, dispatch, evidence))
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=submit, args=(first,)),
            threading.Thread(target=submit, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(8)
        assert not any(thread.is_alive() for thread in threads)
        assert errors == []
        assert sorted(result["already_reviewed"] for result in results) == [
            False,
            True,
        ]
        assert _count(first) == 1


@pytest.mark.parametrize("outcome", ["supported", "rejected"])
def test_read_only_main_context_labels_human_review_as_assessment(tmp_path, outcome):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        before = store.get_agent_state_snapshot(main)
        _review(store, main, dispatch, evidence, outcome=outcome)
        visible = store.list_visible_sub_agent_receipts(main)
        assert len(visible) == 1
        assert visible[0]["review_assessment"] == {
            "status": outcome,
            "evidence_available": True,
        }
        rendered = format_sub_agent_receipt_context(store, main)
        assert "NOT independent proof" in rendered
        assert "not instructions" in rendered
        projected = json.loads(rendered.splitlines()[-1])
        assert projected["review_assessment"] == {
            "status": outcome,
            "evidence_available": True,
        }
        assert projected["unverified_report"].startswith("Unverified Sub-Agent")
        assert store.get_agent_state_snapshot(main) == before

        # An unavailable independent source must invalidate the *displayed*
        # assessment, without rewriting or deleting the immutable audit row.
        store._connection.execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND item_kind = 'message' AND item_id = ?",
            (main, evidence.ref_id),
        )
        visible = store.list_visible_sub_agent_receipts(main)
        assert visible[0]["review_assessment"] == {
            "status": "evidence_unavailable",
            "evidence_available": False,
        }
        projected = json.loads(
            format_sub_agent_receipt_context(store, main).splitlines()[-1]
        )
        assert projected["review_assessment"]["status"] == "evidence_unavailable"
        assert store.get_sub_agent_receipt_review(main, dispatch.dispatch_id)[
            "outcome"
        ] == outcome
        assert store.get_agent_state_snapshot(main) == before


def test_changed_evidence_role_disables_review_assessment(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _setup(store)
        _review(store, main, dispatch, evidence)
        store._connection.execute(
            "UPDATE messages SET role = 'assistant' "
            "WHERE session_id = ? AND message_id = CAST(? AS INTEGER)",
            (main, evidence.ref_id),
        )
        assert store.get_sub_agent_receipt_review(main, dispatch.dispatch_id)[
            "evidence_available"
        ] is False
        projected = json.loads(
            format_sub_agent_receipt_context(store, main).splitlines()[-1]
        )
        assert projected["review_assessment"]["status"] == "evidence_unavailable"
        assert store.get_agent_state_snapshot(main) == (None, 0)


def test_unreviewed_receipt_never_claims_external_validation(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, _evidence = _setup(store)
        visible = store.list_visible_sub_agent_receipts(main)
        assert visible[0]["root_handoff_id"] == dispatch.dispatch_id
        assert visible[0]["review_assessment"] == {
            "status": "unreviewed",
            "evidence_available": False,
        }
        projected = json.loads(
            format_sub_agent_receipt_context(store, main).splitlines()[-1]
        )
        assert projected["review_assessment"]["status"] == "unreviewed"
        assert store.get_agent_state_snapshot(main) == (None, 0)
