"""Reviewed Sub-Agent roots enter Main as metadata, never confirmed facts."""

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


def _prepare(store, *, session_id=None, outcome="supported"):
    if session_id is None:
        session_id = store.create_session(project="test", entry_point="cli").session_id
    store.append_message(
        session_id, "user", "Independent operator evidence: checked externally"
    )
    user_item = store.list_indexed_messages(session_id)[-1]
    evidence_ref = SourceRef(
        "message", user_item["ref_id"], session_id, user_item["session_seq"]
    )
    dispatch = capture_sub_agent_dispatch(
        store,
        receiving_session_id=session_id,
        objective="Investigate a report",
        task_scope="Read-only",
        source_access_check=lambda _ref: False,
    )
    dispatch.record_result(
        json.dumps(
            {
                "status": "completed",
                "summary": "Unconfirmed model report: DO NOT auto-complete",
            }
        )
    )
    receive_compact_sub_agent_return(
        dispatch, agent_role="reviewer", source_access_check=lambda _ref: True
    )
    store.review_sub_agent_receipt(
        session_id,
        dispatch.dispatch_id,
        reviewer_id="operator:local",
        outcome=outcome,
        evidence_refs=(evidence_ref,),
        expected_revision=store.get_agent_state_revision(session_id),
        source_access_check=lambda _ref: True,
    )
    return session_id, dispatch, evidence_ref


def _apply(store, main, dispatch, **changes):
    options = {
        "expected_revision": store.get_agent_state_revision(main),
        "source_access_check": lambda _ref: True,
    }
    options.update(changes)
    return store.apply_reviewed_sub_agent_receipt(main, dispatch.dispatch_id, **options)


def _entry(store, session_id, root):
    state, revision = store.get_agent_state_snapshot(session_id)
    return state["sub_agent_review_registry"]["entries"][root], revision


def test_review_metadata_applies_atomically_without_promoting_report(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _prepare(store)
        assert store.get_agent_state_snapshot(main) == (None, 0)
        result = _apply(store, main, dispatch)
        assert result == {
            "root_handoff_id": dispatch.dispatch_id,
            "already_applied": False,
            "result_revision": 1,
        }
        entry, revision = _entry(store, main, dispatch.dispatch_id)
        assert revision == 1
        assert entry == {
            "status": "reviewed_unverified",
            "reviewer_id": "operator:local",
            "review_base_revision": 0,
            "evidence_refs": [evidence.to_dict()],
        }
        state = store.get_agent_state(main)
        assert "DO NOT auto-complete" not in json.dumps(state)
        assert "goals" not in state
        assert "memory" not in state
        assert "structured_compaction" not in state
        assert (
            store.get_sub_agent_receipt_review(main, dispatch.dispatch_id)["outcome"]
            == "supported"
        )


def test_replay_after_restart_and_legacy_save_cannot_erase_registry(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path) as store:
        main, dispatch, evidence = _prepare(store)
        _apply(store, main, dispatch)
        forged = {
            "memory": "new context",
            "sub_agent_review_registry": {"schema_version": 1, "entries": {}},
        }
        store.save_agent_state(main, forged, expected_revision=1)
        assert _entry(store, main, dispatch.dispatch_id)[1] == 2
    with SessionStore(path) as reopened:
        retry = reopened.apply_reviewed_sub_agent_receipt(
            main,
            dispatch.dispatch_id,
            expected_revision=0,
            source_access_check=lambda _ref: False,
        )
        assert retry["already_applied"] is True
        assert retry["result_revision"] == 2
        entry, revision = _entry(reopened, main, dispatch.dispatch_id)
        assert revision == 2
        assert entry["evidence_refs"] == [evidence.to_dict()]
        assert reopened.get_agent_state(main)["memory"] == "new context"


def test_stale_revision_rejects_before_mutation(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _prepare(store)
        store.save_agent_state(main, {"memory": "updated"}, expected_revision=0)
        before = store.get_agent_state_snapshot(main)
        with pytest.raises(SessionRevisionConflict, match="revision"):
            _apply(store, main, dispatch, expected_revision=0)
        assert store.get_agent_state_snapshot(main) == before


def test_missing_review_rejected_and_rejected_outcome_never_applies(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, rejected, _ref = _prepare(store, outcome="rejected")
        before = store.get_agent_state_snapshot(main)
        with pytest.raises(SessionStoreError, match="not supported"):
            _apply(store, main, rejected)
        assert store.get_agent_state_snapshot(main) == before
        other = store.create_session(project="test", entry_point="cli")
        with pytest.raises(SessionStoreError, match="no review owned"):
            _apply(store, other.session_id, rejected)
        assert store.get_agent_state_snapshot(other.session_id) == (None, 0)


def test_revoke_user_evidence_or_child_output_fails_closed(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _prepare(store)
        store._connection.execute(
            "UPDATE session_items SET availability = 'unavailable' "
            "WHERE session_id = ? AND item_kind = 'message' AND item_id = ?",
            (main, evidence.ref_id),
        )
        with pytest.raises(SessionStoreError, match="review evidence"):
            _apply(store, main, dispatch)
        assert store.get_agent_state_snapshot(main) == (None, 0)
        store._connection.execute(
            "UPDATE session_items SET availability = 'available' "
            "WHERE session_id = ? AND item_kind = 'message' AND item_id = ?",
            (main, evidence.ref_id),
        )
        with pytest.raises(SessionStoreError, match="unauthorized"):
            _apply(store, main, dispatch, source_access_check=lambda _ref: False)
        store.delete_session(dispatch.source_session_id)
        with pytest.raises(SessionStoreError, match="child output"):
            _apply(store, main, dispatch)
        assert store.get_agent_state_snapshot(main) == (None, 0)


def test_changed_main_user_message_role_cannot_authorize_application(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _prepare(store)
        store._connection.execute(
            "UPDATE messages SET role = 'assistant' WHERE message_id = ?",
            (int(evidence.ref_id),),
        )
        with pytest.raises(SessionStoreError, match="independent user"):
            _apply(store, main, dispatch)
        assert store.get_agent_state_snapshot(main) == (None, 0)


def test_two_receipt_reviews_get_distinct_entries_and_monotonic_revisions(
    tmp_path,
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, first, _ref = _prepare(store)
        main, second, _another = _prepare(store, session_id=main)
        assert _apply(store, main, first)["result_revision"] == 1
        assert _apply(store, main, second)["result_revision"] == 2
        state, revision = store.get_agent_state_snapshot(main)
        assert revision == 2
        assert set(state["sub_agent_review_registry"]["entries"]) == {
            first.dispatch_id,
            second.dispatch_id,
        }


def test_parallel_receipt_application_exactly_once(tmp_path):
    path = tmp_path / "sessions.sqlite3"
    with SessionStore(path) as first, SessionStore(path) as second:
        main, dispatch, _ref = _prepare(first)
        ready = threading.Barrier(2)
        results = []
        errors = []

        def apply(store):
            try:
                ready.wait(timeout=5)
                results.append(
                    store.apply_reviewed_sub_agent_receipt(
                        main,
                        dispatch.dispatch_id,
                        expected_revision=0,
                        source_access_check=lambda _ref: True,
                    )
                )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=apply, args=(first,)),
            threading.Thread(target=apply, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(8)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors
        assert sorted(x["already_applied"] for x in results) == [False, True]
        assert store_revision(first, main) == 1


def store_revision(store, main):
    return store.get_agent_state_revision(main)


def test_legacy_registry_collision_is_preserved_and_review_can_apply(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _prepare(store)
        legacy = {"custom": ["old", "value"]}
        store.save_agent_state(
            main,
            {
                "sub_agent_review_registry": legacy,
                "legacy_sub_agent_review_registry": "existing field",
            },
            expected_revision=0,
        )
        result = _apply(store, main, dispatch)
        assert result["result_revision"] == 2
        state = store.get_agent_state(main)
        assert state["legacy_sub_agent_review_registry"] == "existing field"
        assert state["legacy_sub_agent_review_registry_2"] == legacy
        registry = state["sub_agent_review_registry"]
        assert registry["owner"] == "uag.runtime.sub_agent.review_registry.v1"
        assert registry["entries"][dispatch.dispatch_id]["evidence_refs"] == [
            evidence.to_dict()
        ]
        store.save_agent_state(
            main,
            {
                "memory": "current",
                "sub_agent_review_registry": {"custom": "try to overwrite"},
            },
            expected_revision=2,
        )
        assert store.get_agent_state(main)["sub_agent_review_registry"] == registry


def test_old_owner_shaped_data_cannot_forge_application(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        main, dispatch, evidence = _prepare(store)
        forged = {
            "owner": "uag.runtime.sub_agent.review_registry.v1",
            "schema_version": 1,
            "entries": {
                dispatch.dispatch_id: {
                    "status": "reviewed_unverified",
                    "reviewer_id": "operator:local",
                    "review_base_revision": 0,
                    "evidence_refs": [evidence.to_dict()],
                }
            },
        }
        # Before the new feature, a caller was allowed to use this exact
        # JSON shape as arbitrary user state. It is not an ownership grant.
        store.save_agent_state(
            main, {"sub_agent_review_registry": forged}, expected_revision=0
        )
        assert store.get_agent_state(main)["sub_agent_review_registry"] == forged
        assert (
            store._connection.execute(
                "SELECT count(*) FROM sub_agent_review_registry_owners"
            ).fetchone()[0]
            == 0
        )
        result = _apply(store, main, dispatch)
        assert result["already_applied"] is False
        assert result["result_revision"] == 2
        state = store.get_agent_state(main)
        assert state["legacy_sub_agent_review_registry"] == forged
        assert (
            state["sub_agent_review_registry"]["entries"][dispatch.dispatch_id]
            == forged["entries"][dispatch.dispatch_id]
        )
        assert (
            store._connection.execute(
                "SELECT count(*) FROM sub_agent_review_registry_owners"
            ).fetchone()[0]
            == 1
        )

        # Only the separate SQLite marker now protects this registry from
        # ordinary writes; model/user state cannot erase the reviewed root.
        store.save_agent_state(
            main,
            {"sub_agent_review_registry": {}, "memory": "updated"},
            expected_revision=2,
        )
        assert (
            store.get_agent_state(main)["sub_agent_review_registry"]["entries"][
                dispatch.dispatch_id
            ]
            == forged["entries"][dispatch.dispatch_id]
        )
        assert _apply(store, main, dispatch)["already_applied"] is True
