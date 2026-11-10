from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from uagent.nostr_nip17 import _public_key_x, create_nip17_private_messages
from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_outbox import SQLiteNostrOutboxStore
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.nostr_remote_runtime import NostrRemoteRuntime


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def test_retry_worker_claims_and_delivers_a_due_reply(tmp_path, monkeypatch) -> None:
    local_key = _secret(2)
    sender_key = _secret(1)
    sender_pubkey = _public_key_x(sender_key).hex()
    local_pubkey = _public_key_x(local_key).hex()
    now = int(time.time())
    events = create_nip17_private_messages(
        "Reply body", local_key, bytes.fromhex(sender_pubkey), now=now
    )
    routes = {
        sender_pubkey: ["wss://relay.example"],
        local_pubkey: ["wss://relay.example"],
    }
    inbox = SQLiteNostrInboxStore(tmp_path / "worker-inbox.sqlite3")
    outbox = SQLiteNostrOutboxStore(tmp_path / "worker-outbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "worker-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=now)
    request_id = "ab" * 32
    outbox.enqueue(sender_pubkey, request_id, events, routes, created_at=now)
    runtime = NostrRemoteRuntime(
        event_queue=SimpleNamespace(put=lambda _event: None),
        private_key=local_key,
        relays=["wss://relay.example"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        outbox_store=outbox,
    )
    runtime._stop_event = asyncio.Event()
    delivered: list[tuple[str, ...]] = []

    async def fake_deliver(record):
        assert record.status == "sending"
        assert outbox.mark_delivered(
            record.sender_pubkey,
            record.request_rumor_id,
            event_ids=record.event_ids,
        )
        delivered.append(record.event_ids)
        runtime._stop_event.set()
        return {"state": "delivered"}

    monkeypatch.setattr(runtime, "_deliver_outbox_record", fake_deliver)
    try:
        asyncio.run(runtime._retry_outbox())
        assert len(delivered) == 1
        record = outbox.get(sender_pubkey, request_id)
        assert record is not None
        assert record.status == "delivered"
        assert record.events is None
    finally:
        inbox.close()
        outbox.close()
        pairings.close()
