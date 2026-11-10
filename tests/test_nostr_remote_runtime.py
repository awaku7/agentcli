from __future__ import annotations

import queue
import time
from types import SimpleNamespace

import pytest

from uagent.nostr_nip17 import (
    create_nip17_private_messages,
    unwrap_nip17_private_message,
)
from uagent.nostr_remote_dispatch import RemoteCLIRequestError
from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.nostr_remote_runtime import (
    NostrRemoteRuntime,
    dispatch_nostr_remote_inbox_event,
    start_nostr_remote_runtime,
    stop_nostr_remote_runtime,
)


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _setup_request(tmp_path, text: str = "hello"):
    sender_key = _secret(1)
    recipient_key = _secret(2)
    now = int(time.time())
    wrap = create_nip17_private_messages(
        text, sender_key, _public_key_bytes(recipient_key), now=now
    )[0]
    rumor = unwrap_nip17_private_message(wrap, recipient_key)
    inbox = SQLiteNostrInboxStore(tmp_path / "inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "pairings.sqlite3")
    pairings.pair(rumor["pubkey"], "phone", approved=True, paired_at=now)
    inbox.enqueue_verified_wrap(
        rumor["pubkey"],
        rumor["id"],
        wrap,
        created_at=rumor["created_at"],
        received_at=now,
        session_id="active-session",
    )
    event = {
        "kind": "nostr_remote_request",
        "sender_pubkey": rumor["pubkey"],
        "rumor_id": rumor["id"],
        "created_at": rumor["created_at"],
        "session_id": "active-session",
        "text": text,
    }
    return inbox, pairings, recipient_key, event


def _public_key_bytes(secret: bytes) -> bytes:
    from uagent.nostr_nip17 import _public_key_x

    return _public_key_x(secret)


def test_durable_dispatch_stays_claimed_until_foreground_finishes(tmp_path) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        runtime = NostrRemoteRuntime(
            event_queue=queue.Queue(),
            private_key=private_key,
            relays=["wss://relay.example.org"],
            session_id="active-session",
            inbox_store=inbox,
            pairing_store=pairings,
        )
        action = runtime.dispatch_event(event, current_session_id="active-session")
        assert action.kind == "user"
        assert action.text == "hello"
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "dispatching"
        assert record.wrapped_event is not None
        assert runtime.finish_event(event, "completed")
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "completed"
        assert record.wrapped_event is None

        with pytest.raises(RemoteCLIRequestError, match="already claimed"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
    finally:
        inbox.close()
        pairings.close()


def test_durable_dispatch_rejects_revoked_sender_and_finishes_tombstone(
    tmp_path,
) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        assert pairings.revoke(event["sender_pubkey"])
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
        assert record.wrapped_event is None
    finally:
        inbox.close()
        pairings.close()


def test_durable_dispatch_rejects_queue_ciphertext_mismatch(tmp_path) -> None:
    inbox, pairings, private_key, event = _setup_request(tmp_path)
    try:
        event["text"] = "altered message"
        with pytest.raises(RemoteCLIRequestError, match="does not match"):
            dispatch_nostr_remote_inbox_event(
                event,
                inbox_store=inbox,
                pairing_store=pairings,
                private_key=private_key,
                current_session_id="active-session",
            )
        record = inbox.get(event["sender_pubkey"], event["rumor_id"])
        assert record is not None
        assert record.status == "rejected"
    finally:
        inbox.close()
        pairings.close()


def test_listener_runtime_stops_cleanly(tmp_path, monkeypatch) -> None:
    import uagent.nostr_remote_runtime as runtime_module

    async def wait_for_stop(_relay, _key, _callback, *, stop_event, **_kwargs):
        await stop_event.wait()

    monkeypatch.setattr(runtime_module, "listen_nip17_messages", wait_for_stop)
    monkeypatch.setattr("uagent.utils.paths.get_dbs_dir", lambda: tmp_path / "db")
    core = SimpleNamespace(event_queue=queue.Queue(), session_id="active-session")
    runtime = start_nostr_remote_runtime(
        core,
        private_key=_secret(2),
        relays=["wss://relay.example.org"],
    )
    try:
        assert runtime.status()["state"] == "running"
        assert callable(core._nostr_remote_authorize_sender)
        assert stop_nostr_remote_runtime(core)["stopped"]
        assert runtime.status()["state"] == "stopped"
        assert not hasattr(core, "_nostr_remote_runtime")
    finally:
        if not runtime._closed:
            stop_nostr_remote_runtime(core)


def test_invalid_rumor_is_queued_by_reference_without_plaintext(tmp_path) -> None:
    event_queue = queue.Queue()
    inbox = SQLiteNostrInboxStore(tmp_path / "invalid-rumor-inbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "invalid-rumor-pairings.sqlite3")
    runtime = NostrRemoteRuntime(
        event_queue=event_queue,
        private_key=_secret(2),
        relays=["wss://relay.example.org"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
    )
    try:
        runtime._queue_rumor(
            {
                "kind": 14,
                "pubkey": "ab" * 32,
                "id": "cd" * 32,
                "created_at": int(time.time()),
                "content": "",
            }
        )
        queued = event_queue.get_nowait()
        assert queued["kind"] == "nostr_remote_request"
        assert queued["text"] == ""
    finally:
        inbox.close()
        pairings.close()
