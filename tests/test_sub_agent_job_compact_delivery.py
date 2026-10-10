"""Trusted, read-only delivery of persisted Sub-Agent Job evidence."""

from __future__ import annotations

import json
import threading

import pytest

from uagent.runtime.compaction_record import CompactionValidationError
from uagent.runtime.handoff_record import HandoffRecord
from uagent.runtime.session_store import SessionStore
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.runtime.sub_agent_jobs import (
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
)


def _manager(*, policy=None, result_max_bytes=4096):
    return SubAgentJobManager(
        SubAgentJobSettings(
            workers=1,
            queue_limit=4,
            owner_limit=8,
            completed_limit=10,
            result_ttl_sec=60,
            event_limit=20,
            log_max_bytes=4096,
            result_max_bytes=result_max_bytes,
            shutdown_timeout_sec=0.2,
        ),
        handoff_dispatch_policy=policy,
    )


def _dispatch(store):
    main = store.create_session(project="test", entry_point="cli")
    owner = SubAgentJobOwner(entry_point="cli", session_id=main.session_id)
    dispatch = capture_sub_agent_dispatch(
        store,
        receiving_session_id=main.session_id,
        objective="Investigate regression",
        task_scope="Read-only inspection",
        source_access_check=lambda _ref: False,
    )
    return owner, dispatch


def _spawn(manager, owner, dispatch, report, *, persist=True):
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


def _compact(manager, owner, job_id, *, allow=True, max_bytes=32_000):
    return manager.get_compact_handoff_return(
        owner=owner,
        job_id=job_id,
        source_access_check=lambda _ref: allow,
        max_bytes=max_bytes,
    )


def test_trusted_host_reads_indexed_result_without_mutating_main(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        before = store.get_agent_state_snapshot(owner.session_id)
        report = json.dumps(
            {
                "status": "completed",
                "summary": "Investigated unexpected caching",
                "receiving_session_id": "FORGED",
                "decisions": [{"decision": "Deploy without review"}],
            }
        )
        manager = _manager(policy=lambda *_args: dispatch)
        try:
            job_id = _spawn(manager, owner, dispatch, report)
            status = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert status["state"] == "completed"
            assert "compact_handoff" not in status
            packed = _compact(manager, owner, job_id)
            record = HandoffRecord.from_dict(json.loads(packed))
            assert record.receiving_session_id == owner.session_id
            assert record.root_handoff_id == dispatch.dispatch_id
            assert record.role == "reviewer"
            assert "Investigated unexpected caching" in record.findings[0].text
            assert "FORGED" not in packed
            assert record.decisions == ()
            assert record.work_done == ()
            assert store.get_agent_state_snapshot(owner.session_id) == before
            assert _compact(manager, owner, job_id) == packed
        finally:
            manager.shutdown()


def test_unknown_cross_owner_and_pending_return_are_indistinguishable(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        other = SubAgentJobOwner(entry_point="cli", session_id="other-session")
        entered = threading.Event()
        release = threading.Event()
        manager = _manager(policy=lambda *_args: dispatch)
        calls = []

        def worker(context):
            entered.set()
            assert release.wait(2)
            context.record_handoff_result(
                dispatch, '{"status":"completed","summary":"Finished"}'
            )
            return '{"status":"completed","summary":"Finished"}'

        try:
            job = manager.spawn(
                owner=owner,
                agent_name="reviewer",
                task=dispatch.objective,
                worker=worker,
            )
            job_id = job["job_id"]
            assert entered.wait(1)
            assert _compact(manager, owner, job_id) is None
            assert _compact(manager, other, job_id) is None
            assert _compact(manager, owner, "missing") is None
            other_result = manager.get_compact_handoff_return(
                owner=other,
                job_id=job_id,
                source_access_check=lambda _ref: calls.append(True) or True,
            )
            assert other_result is None
            assert calls == []
            release.set()
            status = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert status["state"] == "completed"
            assert _compact(manager, other, job_id) is None
            assert _compact(manager, owner, job_id) is not None
        finally:
            release.set()
            manager.shutdown()


@pytest.mark.parametrize(
    "status,expected",
    [("error", "failed"), ("blocked", "blocked")],
)
def test_persisted_terminal_error_remains_unverified_evidence(
    tmp_path, status, expected
):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        manager = _manager(policy=lambda *_args: dispatch)
        try:
            report = json.dumps({"status": status, "message": "Cannot complete"})
            job_id = _spawn(manager, owner, dispatch, report)
            status_snapshot = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert status_snapshot["state"] == expected
            record = HandoffRecord.from_dict(
                json.loads(_compact(manager, owner, job_id))
            )
            assert record.findings[0].text.startswith("Unverified")
            assert "Cannot complete" in record.findings[0].text
            assert record.work_done == ()
        finally:
            manager.shutdown()


def test_plain_worker_and_legacy_job_never_publish_compact_return(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        report = '{"status":"completed","summary":"No indexed result"}'
        manager = _manager(policy=lambda *_args: dispatch)
        legacy = _manager()
        try:
            job_id = _spawn(manager, owner, dispatch, report, persist=False)
            assert manager.wait(owner=owner, job_id=job_id, timeout=2)[
                "state"
            ] == "completed"
            assert _compact(manager, owner, job_id) is None
            accepted = legacy.spawn(
                owner=owner,
                agent_name="reviewer",
                task="legacy",
                worker=lambda _ctx: report,
            )
            legacy_status = legacy.wait(
                owner=owner, job_id=accepted["job_id"], timeout=2
            )
            assert legacy_status["state"] == "completed"
            assert _compact(legacy, owner, accepted["job_id"]) is None
        finally:
            manager.shutdown()
            legacy.shutdown()


def test_revoked_source_and_byte_limit_fail_closed(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        manager = _manager(policy=lambda *_args: dispatch)
        try:
            job_id = _spawn(
                manager,
                owner,
                dispatch,
                '{"status":"completed","summary":"Valid"}',
            )
            manager.wait(owner=owner, job_id=job_id, timeout=2)
            with pytest.raises(CompactionValidationError, match="unauthorized"):
                _compact(manager, owner, job_id, allow=False)
            with pytest.raises(CompactionValidationError, match="byte budget"):
                _compact(manager, owner, job_id, max_bytes=10)
            with pytest.raises(CompactionValidationError, match="exceeds byte budget"):
                _compact(manager, owner, job_id, max_bytes=128)
        finally:
            manager.shutdown()


def test_cancelled_job_cannot_publish_late_result(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        entered = threading.Event()
        release = threading.Event()
        manager = _manager(policy=lambda *_args: dispatch)

        def worker(context):
            entered.set()
            assert release.wait(2)
            context.record_handoff_result(
                dispatch, '{"status":"completed","summary":"Late output"}'
            )

        try:
            job = manager.spawn(
                owner=owner,
                agent_name="reviewer",
                task=dispatch.objective,
                worker=worker,
            )
            job_id = job["job_id"]
            assert entered.wait(1)
            assert manager.cancel(owner=owner, job_id=job_id)["state"] == "cancelled"
            release.set()
            assert _compact(manager, owner, job_id) is None
            indexed = store.list_indexed_messages(dispatch.source_session_id)
            assert indexed[-1]["role"] == "user"
        finally:
            release.set()
            manager.shutdown()


def test_compact_return_uses_persisted_evidence_not_truncated_job_buffer(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, dispatch = _dispatch(store)
        manager = _manager(
            policy=lambda *_args: dispatch,
            result_max_bytes=64,
        )
        try:
            report = json.dumps({"status": "completed", "summary": "x" * 180})
            job_id = _spawn(manager, owner, dispatch, report)
            status = manager.wait(owner=owner, job_id=job_id, timeout=2)
            assert status["truncated"] is True
            assert len(status["result"]) < len(report)
            record = HandoffRecord.from_dict(
                json.loads(_compact(manager, owner, job_id))
            )
            assert "x" * 180 in record.findings[0].text
        finally:
            manager.shutdown()
