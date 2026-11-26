"""Tests for the CLI loop's per-device chat room binding.

A room-bound device's turn runs in its own session: the loop swaps
the core's session-bound state (the same ``bind_room_session_runtime``
the Web rooms use) and the live message list for the duration of the
turn, then restores the operator's session.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import ec

from uagent.bitchat_pairing import SQLiteBitchatPairingStore
from uagent.cli_impl.main import _enter_chat_room_turn, _leave_chat_room_turn
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.runtime.session_store import SessionStore

NOISE_A = "aa" * 32


def _pubkey(value: int) -> str:
    public_key = ec.derive_private_key(value, ec.SECP256K1()).public_key()
    return public_key.public_numbers().x.to_bytes(32, "big").hex()


def _core(session_id: str, pairing_store) -> SimpleNamespace:
    return SimpleNamespace(
        session_id=session_id,
        SYSTEM_PROMPT="sys-prompt",
        _nostr_remote_runtime=SimpleNamespace(pairing_store=pairing_store),
    )


def test_nostr_room_turn_swaps_and_restores_the_session(tmp_path) -> None:
    from uagent.cli_impl.sub_agent_jobs import SubAgentJobOwner

    sessions = SessionStore(tmp_path / "sessions.sqlite3")
    main = sessions.create_session(project="proj", entry_point="cli")
    with SQLitePairingStore(tmp_path / "pairings.sqlite3") as pairings:
        pairings.pair(_pubkey(51), "phone", approved=True, binding="room")
        core = _core(main.session_id, pairings)
        core._sub_agent_job_owner = SubAgentJobOwner(
            entry_point="cli", session_id=main.session_id
        )
        messages = [
            {"role": "system", "content": "sys-prompt"},
            {"role": "user", "content": "main history"},
        ]
        ctx = _enter_chat_room_turn(
            core,
            sessions,
            messages,
            {"store": "nostr", "peer_key": _pubkey(51)},
            job_owner=core._sub_agent_job_owner,
        )
        assert ctx is not None
        room_session_id = core.session_id
        assert room_session_id != main.session_id
        # The Sub-Agent job owner follows the room session.
        assert core._sub_agent_job_owner.session_id == room_session_id
        assert ctx["job_owner"].session_id == room_session_id
        record = pairings.record_for(_pubkey(51))
        assert record is not None and record.room_session_id == room_session_id
        # The room starts from its own (empty) history plus the
        # current system prompt; the main history is not visible.
        assert [m["content"] for m in messages] == ["sys-prompt"]
        # The turn persists into the room session.
        sessions.append_message(room_session_id, "user", "room hello")
        sessions.append_message(room_session_id, "assistant", "room reply")
        _leave_chat_room_turn(core, messages, ctx)
        assert core.session_id == main.session_id
        assert core._sub_agent_job_owner.session_id == main.session_id
        assert [m["content"] for m in messages] == ["sys-prompt", "main history"]

        # Re-entering reuses the same room and reloads its history.
        ctx = _enter_chat_room_turn(
            core, sessions, messages, {"store": "nostr", "peer_key": _pubkey(51)}
        )
        assert ctx is not None
        assert core.session_id == room_session_id
        contents = [m["content"] for m in messages]
        assert "room hello" in contents and "room reply" in contents
        assert "main history" not in contents
        _leave_chat_room_turn(core, messages, ctx)
        assert core.session_id == main.session_id
    sessions.close()


def test_attach_bound_device_does_not_enter_a_room(tmp_path) -> None:
    sessions = SessionStore(tmp_path / "sessions.sqlite3")
    main = sessions.create_session(project="proj", entry_point="cli")
    with SQLitePairingStore(tmp_path / "pairings.sqlite3") as pairings:
        pairings.pair(_pubkey(52), "phone", approved=True)
        core = _core(main.session_id, pairings)
        messages = [{"role": "user", "content": "main history"}]
        ctx = _enter_chat_room_turn(
            core, sessions, messages, {"store": "nostr", "peer_key": _pubkey(52)}
        )
        assert ctx is None
        assert core.session_id == main.session_id
        assert messages == [{"role": "user", "content": "main history"}]
    sessions.close()


def test_bitchat_room_turn_uses_the_noise_keyed_record(tmp_path, monkeypatch) -> None:
    sessions = SessionStore(tmp_path / "sessions.sqlite3")
    main = sessions.create_session(project="proj", entry_point="cli")
    bitchat_db = tmp_path / "bitchat.sqlite3"

    @contextlib.contextmanager
    def _open():
        with SQLiteBitchatPairingStore(bitchat_db) as store:
            yield store

    monkeypatch.setattr("uagent.bitchat_pairing.open_bitchat_pairing_store", _open)
    with SQLiteBitchatPairingStore(bitchat_db) as pairings:
        pairings.pair(NOISE_A, "peer", approved=True, binding="room")
    core = _core(main.session_id, None)
    messages = [{"role": "user", "content": "main history"}]
    ctx = _enter_chat_room_turn(
        core, sessions, messages, {"store": "bitchat", "peer_key": NOISE_A}
    )
    assert ctx is not None
    assert core.session_id != main.session_id
    with SQLiteBitchatPairingStore(bitchat_db) as pairings:
        record = pairings.record_for(NOISE_A)
        assert record is not None and record.room_session_id == core.session_id
    _leave_chat_room_turn(core, messages, ctx)
    assert core.session_id == main.session_id
    assert messages == [{"role": "user", "content": "main history"}]
    sessions.close()


def test_idle_room_is_forgotten_and_recreated(tmp_path) -> None:
    import sqlite3

    sessions_path = tmp_path / "sessions.sqlite3"
    sessions = SessionStore(sessions_path)
    main = sessions.create_session(project="proj", entry_point="cli")
    with SQLitePairingStore(tmp_path / "pairings.sqlite3") as pairings:
        pairings.pair(_pubkey(71), "phone", approved=True, binding="room")
        core = _core(main.session_id, pairings)
        messages = [{"role": "user", "content": "main history"}]
        descriptor = {"store": "nostr", "peer_key": _pubkey(71)}
        ctx = _enter_chat_room_turn(core, sessions, messages, descriptor)
        assert ctx is not None
        first_room_id = core.session_id
        sessions.append_message(first_room_id, "user", "old room history")
        _leave_chat_room_turn(core, messages, ctx)

        # Age the room past the idle retention (default 24 hours).
        with sqlite3.connect(sessions_path) as conn:
            conn.execute(
                "UPDATE sessions SET last_used_at = '2000-01-01 00:00:00.000' "
                "WHERE session_id = ?",
                (first_room_id,),
            )

        ctx = _enter_chat_room_turn(core, sessions, messages, descriptor)
        assert ctx is not None
        assert core.session_id != first_room_id
        # The fresh room does not load the expired room's history,
        # but the old session itself is kept in the store.
        assert "old room history" not in [m["content"] for m in messages]
        assert sessions.get_session(first_room_id)["session_id"] == first_room_id
        record = pairings.record_for(_pubkey(71))
        assert record is not None and record.room_session_id == core.session_id
        _leave_chat_room_turn(core, messages, ctx)
    sessions.close()


def test_nostr_room_turn_without_a_running_listener(tmp_path, monkeypatch) -> None:
    # BitChat-over-Nostr peers paired only in the Nostr registry keep
    # their room even when the remote listener is not running: the
    # record resolves through the persistent pairing database.
    from uagent.tools import nostr_transport

    sessions = SessionStore(tmp_path / "sessions.sqlite3")
    main = sessions.create_session(project="proj", entry_point="cli")
    pairing_db = tmp_path / "pairings.sqlite3"
    with SQLitePairingStore(pairing_db) as pairings:
        pairings.pair(_pubkey(61), "phone", approved=True, binding="room")
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: pairing_db)
    core = SimpleNamespace(session_id=main.session_id, SYSTEM_PROMPT="sys-prompt")
    messages = [{"role": "user", "content": "main history"}]
    ctx = _enter_chat_room_turn(
        core, sessions, messages, {"store": "nostr", "peer_key": _pubkey(61)}
    )
    assert ctx is not None
    room_session_id = core.session_id
    assert room_session_id != main.session_id
    _leave_chat_room_turn(core, messages, ctx)
    assert core.session_id == main.session_id
    with SQLitePairingStore(pairing_db) as pairings:
        record = pairings.record_for(_pubkey(61))
        assert record is not None and record.room_session_id == room_session_id
    sessions.close()
