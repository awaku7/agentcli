from __future__ import annotations

from uagent.nostr_nip17 import _public_key_x, create_nip17_private_messages
from uagent.nostr_remote_outbox import OutboxFullError, SQLiteNostrOutboxStore

REQUEST_ID = "cd" * 32


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _payload() -> tuple[bytes, list[dict[str, object]], dict[str, list[str]]]:
    sender_key = _secret(1)
    recipient_key = _secret(2)
    sender_pubkey = _public_key_x(sender_key).hex()
    recipient_pubkey = _public_key_x(recipient_key).hex()
    events = create_nip17_private_messages(
        "Private reply body",
        sender_key,
        bytes.fromhex(recipient_pubkey),
        now=1_700_000_000,
    )
    routes = {
        sender_pubkey: ["wss://relay.example"],
        recipient_pubkey: ["wss://relay.example"],
    }
    return sender_key, events, routes


def test_outbox_persists_exact_encrypted_events_and_retries_with_backoff(
    tmp_path,
) -> None:
    sender_key, events, routes = _payload()
    sender = _public_key_x(sender_key).hex()
    path = tmp_path / "remote-outbox.sqlite3"
    store = SQLiteNostrOutboxStore(path)
    try:
        queued = store.enqueue(sender, REQUEST_ID, events, routes, created_at=100)
        assert queued.status == "pending"
        assert queued.events == events
        assert queued.event_ids == tuple(event["id"] for event in events)
        assert store.pending_count() == 1

        claimed = store.claim(sender, REQUEST_ID, now=100)
        assert claimed is not None
        assert claimed.status == "sending"
        assert claimed.attempts == 1

        retry = store.retry_or_fail(sender, REQUEST_ID, "Timeout", now=101)
        assert retry is not None
        assert retry.status == "pending"
        assert retry.next_attempt_at == 106
        assert store.claim(sender, REQUEST_ID, now=105) is None

        reclaimed = store.claim(sender, REQUEST_ID, now=106)
        assert reclaimed is not None
        assert reclaimed.status == "sending"
        assert reclaimed.attempts == 2
        assert reclaimed.events == events
    finally:
        store.close()


def test_outbox_delivery_erases_ciphertext_and_keeps_idempotency_tombstone(
    tmp_path,
) -> None:
    sender_key, events, routes = _payload()
    sender = _public_key_x(sender_key).hex()
    store = SQLiteNostrOutboxStore(tmp_path / "delivered-outbox.sqlite3")
    try:
        store.enqueue(sender, REQUEST_ID, events, routes, created_at=100)
        assert store.claim(sender, REQUEST_ID, now=100) is not None
        event_ids = [event["id"] for event in events]
        assert store.mark_delivered(sender, REQUEST_ID, event_ids=event_ids)

        delivered = store.get(sender, REQUEST_ID)
        assert delivered is not None
        assert delivered.status == "delivered"
        assert delivered.events is None
        assert delivered.relay_lists_by_pubkey is None
        assert delivered.event_ids == tuple(event_ids)

        duplicate = store.enqueue(sender, REQUEST_ID, events, routes, created_at=200)
        assert duplicate.status == "delivered"
        assert duplicate.events is None
        assert store.pending_count() == 0
    finally:
        store.close()


def test_outbox_capacity_fails_closed(tmp_path) -> None:
    sender_key, events, routes = _payload()
    sender = _public_key_x(sender_key).hex()
    store = SQLiteNostrOutboxStore(tmp_path / "bounded-outbox.sqlite3", max_pending=1)
    try:
        store.enqueue(sender, REQUEST_ID, events, routes, created_at=100)
        try:
            store.enqueue(sender, "ef" * 32, events, routes, created_at=101)
        except OutboxFullError:
            pass
        else:
            raise AssertionError("outbox accepted a request beyond its pending cap")
    finally:
        store.close()


def test_outbox_reclaims_expired_sending_lease_after_restart(tmp_path) -> None:
    sender_key, events, routes = _payload()
    sender = _public_key_x(sender_key).hex()
    path = tmp_path / "recovery-outbox.sqlite3"
    store = SQLiteNostrOutboxStore(path, sending_lease_seconds=10)
    store.enqueue(sender, REQUEST_ID, events, routes, created_at=100)
    first_claim = store.claim(sender, REQUEST_ID, now=100)
    assert first_claim is not None
    store.close()

    reopened = SQLiteNostrOutboxStore(path, sending_lease_seconds=10)
    try:
        recovered = reopened.claim_next_due(now=111)
        assert recovered is not None
        assert recovered.status == "sending"
        assert recovered.attempts == 2
        assert recovered.event_ids == first_claim.event_ids
    finally:
        reopened.close()
