"""Explicit CLI receipt reviews are operator-scoped and audit-only."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from uagent.cli_impl import sub_agent_receipt_review as cli_review
from uagent.runtime.session_store import SessionStore
from uagent.runtime.sub_agent_handoff import capture_sub_agent_dispatch
from uagent.runtime.sub_agent_jobs import SubAgentJobOwner
from uagent.runtime.sub_agent_receipt import receive_compact_sub_agent_return


def _setup(store):
    parent = store.create_session(project="test", entry_point="cli")
    main_id = parent.session_id
    store.append_message(main_id, "user", "Independent local evidence")
    evidence = store.list_indexed_messages(main_id)[-1]
    dispatch = capture_sub_agent_dispatch(
        store,
        receiving_session_id=main_id,
        objective="Investigate issue",
        task_scope="Read-only",
        source_access_check=lambda _ref: False,
    )
    dispatch.record_result(
        json.dumps({"status": "completed", "summary": "Needs review"})
    )
    receive_compact_sub_agent_return(
        dispatch,
        agent_role="reviewer",
        source_access_check=lambda _ref: True,
    )
    core = SimpleNamespace(
        _session_store_active_id=main_id,
        auto_pilot_active=False,
    )
    owner = SubAgentJobOwner(entry_point="cli", session_id=main_id)
    command = (
        f":receipt review {dispatch.dispatch_id} supported "
        f"{evidence['ref_id']} {evidence['session_seq']}"
    )
    return core, owner, dispatch, evidence, command


def test_review_command_requires_local_operator(tmp_path, monkeypatch, capsys):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, _evidence, command = _setup(store)
        assert not cli_review.handle_cli_receipt_command(
            ":jobs", core=core, store=store, owner=owner
        )
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: False)
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        assert "requires an interactive local operator" in capsys.readouterr().out
        assert (
            store.get_sub_agent_receipt_review(owner.session_id, dispatch.dispatch_id)
            is None
        )


def test_explicit_review_is_audit_only_and_idempotent(tmp_path, monkeypatch, capsys):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, evidence, command = _setup(store)
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: True)
        before = store.get_agent_state_snapshot(owner.session_id)
        assert cli_review.handle_cli_receipt_command(
            ":receipt", core=core, store=store, owner=owner
        )
        assert dispatch.dispatch_id in capsys.readouterr().out
        assert cli_review.handle_cli_receipt_command(
            ":receipt evidence", core=core, store=store, owner=owner
        )
        candidates = capsys.readouterr().out
        assert f"message-id={evidence['ref_id']}" in candidates
        assert "Independent local evidence" not in candidates

        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        assert "audit only" in capsys.readouterr().out
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        assert "already recorded" in capsys.readouterr().out
        audit = store.get_sub_agent_receipt_review(
            owner.session_id, dispatch.dispatch_id
        )
        assert audit["outcome"] == "supported"
        assert audit["reviewer_id"] == "cli:local-operator"
        assert store.get_agent_state_snapshot(owner.session_id) == before


def test_switching_sessions_or_auto_mode_cannot_register_review(
    tmp_path, monkeypatch, capsys
):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, _evidence, command = _setup(store)
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: True)
        different = store.create_session(project="test", entry_point="cli")
        core._session_store_active_id = different.session_id
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        assert "unavailable" in capsys.readouterr().out
        core._session_store_active_id = owner.session_id
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: False)
        core.auto_pilot_active = True
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        assert "interactive local operator" in capsys.readouterr().out
        assert (
            store.get_sub_agent_receipt_review(owner.session_id, dispatch.dispatch_id)
            is None
        )


def test_rejects_invalid_independent_evidence_and_conflicting_replay(
    tmp_path, monkeypatch, capsys
):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, evidence, command = _setup(store)
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: True)
        bad = f":receipt review {dispatch.dispatch_id} supported 99999 12"
        assert cli_review.handle_cli_receipt_command(
            bad, core=core, store=store, owner=owner
        )
        assert "rejected" in capsys.readouterr().out
        assert cli_review.handle_cli_receipt_command(
            ":receipt review invalid supported nan nan",
            core=core,
            store=store,
            owner=owner,
        )
        assert "Invalid" in capsys.readouterr().out
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        capsys.readouterr()
        conflicting = (
            f":receipt review {dispatch.dispatch_id} rejected "
            f"{evidence['ref_id']} {evidence['session_seq']}"
        )
        assert cli_review.handle_cli_receipt_command(
            conflicting, core=core, store=store, owner=owner
        )
        assert "rejected: SessionStoreError" in capsys.readouterr().out
        audit = store.get_sub_agent_receipt_review(
            owner.session_id, dispatch.dispatch_id
        )
        assert audit["outcome"] == "supported"


def test_interactive_gate_disallows_headless_and_auto_mode(monkeypatch):
    fake = SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(cli_review, "sys", SimpleNamespace(stdin=fake, stdout=fake))
    monkeypatch.delenv("UAGENT_NON_INTERACTIVE", raising=False)
    assert cli_review._human_review_available(SimpleNamespace(auto_pilot_active=False))
    assert not cli_review._human_review_available(
        SimpleNamespace(auto_pilot_active=True)
    )
    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    assert not cli_review._human_review_available(
        SimpleNamespace(auto_pilot_active=False)
    )


@pytest.mark.parametrize(
    "cmd",
    [
        ":receipt review",
        ":receipt review a unknown 3 1",
        ":receipt review a supported 3 0",
        ":receipt review a supported 3 one",
        ":receipt review missing-root supported 1 1 extra",
    ],
)
def test_malformed_commands_do_not_create_reviews(tmp_path, monkeypatch, cmd):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, _evidence, _command = _setup(store)
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: True)
        assert cli_review.handle_cli_receipt_command(
            cmd, core=core, store=store, owner=owner
        )
        assert (
            store.get_sub_agent_receipt_review(owner.session_id, dispatch.dispatch_id)
            is None
        )


def test_cli_command_events_release_busy_state_even_after_rejection(
    tmp_path, monkeypatch
):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, _dispatch, _evidence, command = _setup(store)
        core.status_busy = True

        def set_status(busy, _label):
            core.status_busy = busy

        core.set_status = set_status
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: False)
        assert not cli_review.dispatch_cli_receipt_command_event(
            ":jobs", core=core, store=store, owner=owner
        )
        assert core.status_busy
        assert cli_review.dispatch_cli_receipt_command_event(
            ":receipt evidence", core=core, store=store, owner=owner
        )
        assert not core.status_busy
        core.status_busy = True
        assert cli_review.dispatch_cli_receipt_command_event(
            command, core=core, store=store, owner=owner
        )
        assert not core.status_busy


def test_identical_cli_review_retry_after_main_revision_advances(
    tmp_path, monkeypatch, capsys
):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, _evidence, command = _setup(store)
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: True)
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        capsys.readouterr()
        store.save_agent_state(
            owner.session_id, {"memory": "later"}, expected_revision=0
        )
        assert cli_review.handle_cli_receipt_command(
            command, core=core, store=store, owner=owner
        )
        assert "already recorded" in capsys.readouterr().out
        record = store.get_sub_agent_receipt_review(
            owner.session_id, dispatch.dispatch_id
        )
        assert record["base_revision"] == 0
        assert store.get_agent_state_revision(owner.session_id) == 1


def test_oversized_sqlite_sequence_is_rejected_without_crashing(
    tmp_path, monkeypatch, capsys
):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        core, owner, dispatch, evidence, _command = _setup(store)
        monkeypatch.setattr(cli_review, "_human_review_available", lambda _core: True)
        malformed = (
            f":receipt review {dispatch.dispatch_id} supported "
            f"{evidence['ref_id']} 999999999999999999999999"
        )
        assert cli_review.handle_cli_receipt_command(
            malformed, core=core, store=store, owner=owner
        )
        assert "Invalid" in capsys.readouterr().out
        assert (
            store.get_sub_agent_receipt_review(owner.session_id, dispatch.dispatch_id)
            is None
        )


def test_new_cli_messages_flow_through_host_translation(tmp_path, monkeypatch, capsys):
    with SessionStore(tmp_path / "session.sqlite3") as store:
        main = store.create_session(project="test", entry_point="cli")
        owner = SubAgentJobOwner(entry_point="cli", session_id=main.session_id)
        core = SimpleNamespace(_session_store_active_id=main.session_id)
        monkeypatch.setattr(cli_review, "_", lambda value: "[translated] " + value)
        assert cli_review.handle_cli_receipt_command(
            ":receipt", core=core, store=store, owner=owner
        )
        assert "[translated] No currently accessible" in capsys.readouterr().out
