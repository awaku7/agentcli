"""CLI foreground Job completion delivery is opt-in and scope-limited."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from uagent.runtime.compaction_record import CompactionValidationError
from uagent.runtime.session_store import SessionRevisionConflict, SessionStore
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.runtime.sub_agent_receipt import receive_compact_sub_agent_return
from uagent.runtime.sub_agent_cli_receipt import (
    cli_auto_receipt_enabled,
    deliver_cli_finished_job_notice,
)
from uagent.runtime.sub_agent_host_policy import build_scoped_job_handoff_policy
from uagent.runtime.sub_agent_receipt_context import (
    cli_receipt_context_enabled,
    format_sub_agent_receipt_context,
    inject_sub_agent_receipt_context,
    queue_cli_sub_agent_receipt,
)
from uagent.runtime.sub_agent_jobs import (
    SubAgentJobManager,
    SubAgentJobOwner,
    SubAgentJobSettings,
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


def _setup(store, *, structured=True):
    parent = store.create_session(project="test", entry_point="cli")
    owner = SubAgentJobOwner(entry_point="cli", session_id=parent.session_id)
    notices = []
    finished = threading.Event()

    def on_notice(notice):
        notices.append(notice)
        if notice.get("event") == "finished":
            finished.set()

    manager = SubAgentJobManager(
        _settings(),
        notice_callback=on_notice,
        handoff_dispatch_policy=(
            build_scoped_job_handoff_policy(store, entry_point="cli")
            if structured
            else None
        ),
    )
    return owner, manager, notices, finished


def _spawn(manager, owner, *, structured=True):
    report = '{"status":"completed","summary":"Needs verification"}'

    def worker(context):
        if structured:
            context.record_handoff_result(context.handoff_dispatch, report)
        return report

    accepted = manager.spawn(
        owner=owner,
        agent_name="reviewer",
        task="Inspect an issue",
        worker=worker,
    )
    assert accepted["status"] == "accepted"
    return accepted["job_id"]


def _finished_notice(manager, owner, notices, finished, job_id):
    job = manager.wait(owner=owner, job_id=job_id, timeout=3)
    assert job["state"] == "completed"
    assert finished.wait(3)
    return next(
        notice
        for notice in notices
        if notice["job_id"] == job_id and notice["event"] == "finished"
    )


def _count(store):
    return store._connection.execute(
        "SELECT count(*) FROM sub_agent_receipts"
    ).fetchone()[0]


def test_cli_auto_receipt_follows_structured_opt_in():
    assert not cli_auto_receipt_enabled({}, structured_handoff_enabled=False)
    assert cli_auto_receipt_enabled({}, structured_handoff_enabled=True)
    assert not cli_auto_receipt_enabled(
        {"UAGENT_SUB_AGENT_HANDOFF_AUTO_RECEIPT": "0"},
        structured_handoff_enabled=True,
    )
    assert cli_auto_receipt_enabled(
        {"UAGENT_SUB_AGENT_HANDOFF_AUTO_RECEIPT": "1"},
        structured_handoff_enabled=True,
    )
    with pytest.raises(ValueError, match="requires structured"):
        cli_auto_receipt_enabled(
            {"UAGENT_SUB_AGENT_HANDOFF_AUTO_RECEIPT": "1"},
            structured_handoff_enabled=False,
        )
    with pytest.raises(ValueError, match="must be 0 or 1"):
        cli_auto_receipt_enabled(
            {"UAGENT_SUB_AGENT_HANDOFF_AUTO_RECEIPT": "maybe"},
            structured_handoff_enabled=True,
        )


def test_single_structured_opt_in_shares_unverified_results_with_main(tmp_path):
    # The user enables one structured mode, not separate delivery/context flags.
    environment = {"UAGENT_SUB_AGENT_STRUCTURED_HANDOFF": "1"}
    assert cli_auto_receipt_enabled(environment, structured_handoff_enabled=True)
    assert cli_receipt_context_enabled(environment, structured_handoff_enabled=True)

    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, manager, notices, finished = _setup(store)
        before = store.get_agent_state_snapshot(owner.session_id)
        try:
            job_id = _spawn(manager, owner)
            notice = _finished_notice(manager, owner, notices, finished, job_id)
            received = deliver_cli_finished_job_notice(
                manager=manager, owner=owner, notice=notice, store=store
            )
            assert received["receiving_session_id"] == owner.session_id
            context = format_sub_agent_receipt_context(store, owner.session_id)
            assert "UNVERIFIED" in context
            assert "Needs verification" in context
            assert "not instructions" in context
            core = SimpleNamespace(
                session_store=store,
                _session_store_active_id=owner.session_id,
                _sub_agent_job_owner=owner,
                _sub_agent_receipt_context_enabled=True,
            )
            next_turn = [{"role": "user", "content": "Continue"}]
            queue_cli_sub_agent_receipt(core, received)
            assert inject_sub_agent_receipt_context(next_turn, core)
            assert "Needs verification" in next_turn[0]["content"]
            assert not inject_sub_agent_receipt_context(
                [{"role": "user", "content": "Unrelated"}], core
            )
            assert store.get_agent_state_snapshot(owner.session_id) == before
            assert store.list_indexed_messages(owner.session_id) == []
        finally:
            manager.shutdown()


def test_cli_notice_auto_receipts_only_unverified_evidence_and_retries(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, manager, notices, finished = _setup(store)
        before = store.get_agent_state_snapshot(owner.session_id)
        try:
            job_id = _spawn(manager, owner)
            notice = _finished_notice(manager, owner, notices, finished, job_id)
            first = deliver_cli_finished_job_notice(
                manager=manager, owner=owner, notice=notice, store=store
            )
            assert first["receiving_session_id"] == owner.session_id
            assert first["already_received"] is False
            second = deliver_cli_finished_job_notice(
                manager=manager, owner=owner, notice=notice, store=store
            )
            assert second["already_received"] is True
            assert _count(store) == 1
            assert store.get_agent_state_snapshot(owner.session_id) == before
            saved = store._connection.execute(
                "SELECT record_json FROM sub_agent_receipts"
            ).fetchone()["record_json"]
            assert "Unverified Sub-Agent report" in saved
            assert "Needs verification" in saved
            assert store.list_indexed_messages(owner.session_id) == []
        finally:
            manager.shutdown()


def test_notice_does_not_deliver_to_switched_owner_or_on_start(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, manager, notices, finished = _setup(store)
        try:
            job_id = _spawn(manager, owner)
            notice = _finished_notice(manager, owner, notices, finished, job_id)
            switched_session = store.create_session(project="test", entry_point="cli")
            switched = SubAgentJobOwner(
                entry_point="cli", session_id=switched_session.session_id
            )
            assert (
                deliver_cli_finished_job_notice(
                    manager=manager, owner=switched, notice=notice, store=store
                )
                is None
            )
            started = next(
                n for n in notices if n["event"] == "started" and n["job_id"] == job_id
            )
            assert (
                deliver_cli_finished_job_notice(
                    manager=manager, owner=owner, notice=started, store=store
                )
                is None
            )
            assert _count(store) == 0
        finally:
            manager.shutdown()


def test_unstructured_job_and_forged_notice_do_not_deliver(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, manager, notices, finished = _setup(store, structured=False)
        try:
            job_id = _spawn(manager, owner, structured=False)
            notice = _finished_notice(manager, owner, notices, finished, job_id)
            assert (
                deliver_cli_finished_job_notice(
                    manager=manager, owner=owner, notice=notice, store=store
                )
                is None
            )
            forged = dict(notice)
            forged["owner"] = dict(notice["owner"], session_id="another")
            assert (
                deliver_cli_finished_job_notice(
                    manager=manager, owner=owner, notice=forged, store=store
                )
                is None
            )
            assert _count(store) == 0
        finally:
            manager.shutdown()


def test_stale_direct_receipt_still_rejected_without_job_ownership(tmp_path):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main = store.create_session(project="test", entry_point="cli").session_id
        dispatch = capture_sub_agent_dispatch(
            store,
            receiving_session_id=main,
            objective="Inspect",
            task_scope="Read-only",
            source_access_check=lambda _ref: False,
        )
        dispatch.record_result('{"status":"completed","summary":"Inspect result"}')
        store.save_agent_state(main, {"memory": "newer"}, expected_revision=0)
        before = store.get_agent_state_snapshot(main)
        with pytest.raises(SessionRevisionConflict):
            receive_compact_sub_agent_return(
                dispatch,
                agent_role="reviewer",
                source_access_check=lambda _ref: True,
            )
        assert store.get_agent_state_snapshot(main) == before


def test_stale_main_revision_keeps_unverified_receipt_and_revocation_fails_closed(tmp_path):
    with SessionStore(tmp_path / "sessions.sqlite3") as store:
        owner, manager, notices, finished = _setup(store)
        try:
            job_id = _spawn(manager, owner)
            notice = _finished_notice(manager, owner, notices, finished, job_id)
            store.save_agent_state(
                owner.session_id, {"memory": "newer"}, expected_revision=0
            )
            before = store.get_agent_state_snapshot(owner.session_id)
            receipt = deliver_cli_finished_job_notice(
                manager=manager, owner=owner, notice=notice, store=store
            )
            assert receipt["receiving_session_id"] == owner.session_id
            assert receipt["already_received"] is False
            assert store.get_agent_state_snapshot(owner.session_id) == before
            assert _count(store) == 1
            rendered = format_sub_agent_receipt_context(store, owner.session_id)
            assert "Needs verification" in rendered
            assert '"base_revision": 0' in rendered
        finally:
            manager.shutdown()
    with SessionStore(tmp_path / "revoked.sqlite3") as store:
        owner, manager, notices, finished = _setup(store)
        try:
            job_id = _spawn(manager, owner)
            notice = _finished_notice(manager, owner, notices, finished, job_id)
            store._connection.execute(
                "UPDATE session_items SET availability = 'unavailable' "
                "WHERE session_id IN "
                "(SELECT session_id FROM sessions WHERE entry_point = 'sub-agent') "
                "AND item_kind = 'message' AND item_id IN "
                "(SELECT CAST(message_id AS TEXT) FROM messages "
                "WHERE role = 'assistant')"
            )
            with pytest.raises(CompactionValidationError):
                deliver_cli_finished_job_notice(
                    manager=manager, owner=owner, notice=notice, store=store
                )
            assert _count(store) == 0
        finally:
            manager.shutdown()
