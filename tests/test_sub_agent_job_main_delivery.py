"""Trusted Job-to-Main receipt delivery without AgentState application."""

from __future__ import annotations

import json
import threading

import pytest

from uagent.runtime.compaction_record import CompactionValidationError
from uagent.runtime.session_store import SessionRevisionConflict, SessionStore
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.runtime.sub_agent_jobs import (
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
)


def _setup(store):
    main = store.create_session(project="test", entry_point="cli")
    owner = SubAgentJobOwner(entry_point="cli", session_id=main.session_id)
    dispatch = capture_sub_agent_dispatch(
        store,
        receiving_session_id=main.session_id,
        objective="Investigate failures",
        task_scope="Read-only",
        source_access_check=lambda _ref: False,
    )
    manager = SubAgentJobManager(
        SubAgentJobSettings(
            workers=1,
            queue_limit=4,
            owner_limit=4,
            completed_limit=8,
            result_ttl_sec=60,
            event_limit=10,
            log_max_bytes=4096,
            result_max_bytes=64,
            shutdown_timeout_sec=0.2,
        ),
        handoff_dispatch_policy=lambda *_args: dispatch,
    )
    return owner, dispatch, manager


def _start(manager, owner, dispatch, report, *, persist=True):
    def worker(context):
        if persist:
            context.record_handoff_result(dispatch, report)
        return report

    accepted = manager.spawn(
        owner=owner,
        agent_name="reviewer",
        task=dispatch.objective,
        worker=worker,
    )
    assert accepted["status"] == "accepted"
    return accepted["job_id"]


def _deliver(manager, owner, job_id, *, allowed=True):
    return manager.deliver_compact_handoff_to_main(
        owner=owner,
        job_id=job_id,
        source_access_check=lambda _ref: allowed,
    )


def _receipt_count(store):
    row = store._connection.execute(
        "SELECT count(*) FROM sub_agent_receipts"
    ).fetchone()
    return row[0]


def test_trusted_delivery_is_idempotent_and_does_not_modify_main(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch, manager = _setup(store)
        report = json.dumps(
            {
                "status": "completed",
                "summary": "Cache may be stale",
                "receiving_session_id": "model-forged-receiver",
                "decisions": ["fake decision"],
            }
        )
        before = store.get_agent_state_snapshot(owner.session_id)
        try:
            job_id = _start(manager, owner, dispatch, report)
            finished = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert finished["state"] == "completed"
            first = _deliver(manager, owner, job_id)
            assert first == {
                "receiving_session_id": owner.session_id,
                "root_handoff_id": dispatch.dispatch_id,
                "already_received": False,
            }
            second = _deliver(manager, owner, job_id)
            assert second["already_received"] is True
            assert _receipt_count(store) == 1
            assert store.get_agent_state_snapshot(owner.session_id) == before
            assert store.list_indexed_messages(owner.session_id) == []
            assert "compact_handoff" not in finished
            saved = store._connection.execute(
                "SELECT record_json FROM sub_agent_receipts"
            ).fetchone()["record_json"]
            assert "model-forged-receiver" not in saved
            assert "fake decision" not in saved
            assert "Unverified Sub-Agent report" in saved
        finally:
            manager.shutdown()


def test_pending_other_owner_missing_and_unpersisted_jobs_do_not_deliver(
    tmp_path,
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch, manager = _setup(store)
        other = SubAgentJobOwner(entry_point="cli", session_id="another-session")
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def worker(context):
            entered.set()
            assert release.wait(2)
            return '{"status":"completed","summary":"No indexed output"}'

        try:
            accepted = manager.spawn(
                owner=owner,
                agent_name="reviewer",
                task=dispatch.objective,
                worker=worker,
            )
            job_id = accepted["job_id"]
            assert entered.wait(1)
            for current_owner, current_id in (
                (other, job_id),
                (owner, "unknown-job"),
                (owner, job_id),
            ):
                receipt = manager.deliver_compact_handoff_to_main(
                    owner=current_owner,
                    job_id=current_id,
                    source_access_check=lambda _ref: calls.append(True) or True,
                )
                assert receipt is None
            assert calls == []
            release.set()
            finished = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert finished["state"] == "completed"
            assert _deliver(manager, owner, job_id) is None
            assert _receipt_count(store) == 0
        finally:
            release.set()
            manager.shutdown()


def test_stale_main_revision_rejects_delivery_without_receipt(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch, manager = _setup(store)
        try:
            job_id = _start(
                manager,
                owner,
                dispatch,
                '{"status":"completed","summary":"Done"}',
            )
            manager.wait(owner=owner, job_id=job_id, timeout=2)
            store.save_agent_state(
                owner.session_id, {"memory": "newer"}, expected_revision=0
            )
            before = store.get_agent_state_snapshot(owner.session_id)
            with pytest.raises(SessionRevisionConflict, match="older"):
                _deliver(manager, owner, job_id)
            assert _receipt_count(store) == 0
            assert store.get_agent_state_snapshot(owner.session_id) == before
        finally:
            manager.shutdown()


def test_revoked_output_source_fails_closed_without_receipt(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch, manager = _setup(store)
        try:
            job_id = _start(
                manager,
                owner,
                dispatch,
                '{"status":"completed","summary":"Done"}',
            )
            manager.wait(owner=owner, job_id=job_id, timeout=2)
            with pytest.raises(CompactionValidationError, match="unauthorized"):
                _deliver(manager, owner, job_id, allowed=False)
            assert _receipt_count(store) == 0
            assert _deliver(manager, owner, job_id)["already_received"] is False
        finally:
            manager.shutdown()


@pytest.mark.parametrize(
    "status,job_state",
    [("blocked", "blocked"), ("error", "failed")],
)
def test_terminal_error_is_delivered_only_as_unverified_report(
    tmp_path, status, job_state
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch, manager = _setup(store)
        try:
            report = json.dumps({"status": status, "message": "Cannot complete"})
            job_id = _start(manager, owner, dispatch, report)
            snapshot = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert snapshot["state"] == job_state
            receipt = _deliver(manager, owner, job_id)
            assert receipt["already_received"] is False
            saved = store._connection.execute(
                "SELECT record_json FROM sub_agent_receipts"
            ).fetchone()["record_json"]
            assert "Unverified Sub-Agent report" in saved
            assert "Cannot complete" in saved
            assert store.get_agent_state_snapshot(owner.session_id) == (None, 0)
        finally:
            manager.shutdown()


def test_cancelled_job_cannot_deliver_late_output(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch, manager = _setup(store)
        entered = threading.Event()
        release = threading.Event()

        def worker(context):
            entered.set()
            assert release.wait(2)
            context.record_handoff_result(
                dispatch, '{"status":"completed","summary":"Too late"}'
            )

        try:
            accepted = manager.spawn(
                owner=owner,
                agent_name="reviewer",
                task=dispatch.objective,
                worker=worker,
            )
            job_id = accepted["job_id"]
            assert entered.wait(1)
            cancelled = manager.cancel(owner=owner, job_id=job_id)
            assert cancelled["state"] == "cancelled"
            release.set()
            assert _deliver(manager, owner, job_id) is None
            assert _receipt_count(store) == 0
        finally:
            release.set()
            manager.shutdown()
