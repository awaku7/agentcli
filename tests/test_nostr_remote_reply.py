from __future__ import annotations

from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import ec

from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
from uagent.nostr_remote_outbox import SQLiteNostrOutboxStore
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.nostr_remote_runtime import NostrRemoteRuntime


def _secret(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _public_key(secret: bytes) -> bytes:
    public_key = ec.derive_private_key(int.from_bytes(secret, "big"), ec.SECP256K1())
    return public_key.public_key().public_numbers().x.to_bytes(32, "big")


def test_reply_uses_verified_recipient_relays_intersected_with_local_allowlist(
    tmp_path, monkeypatch
) -> None:
    from uagent import nostr_remote_transport as transport

    local_key = _secret(2)
    sender_key = _secret(1)
    sender_pubkey = _public_key(sender_key).hex()
    local_relays = ["wss://local-a.example", "wss://local-b.example"]
    inbox = SQLiteNostrInboxStore(tmp_path / "reply-inbox.sqlite3")
    outbox = SQLiteNostrOutboxStore(tmp_path / "reply-outbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "reply-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=100)
    runtime = NostrRemoteRuntime(
        event_queue=SimpleNamespace(put=lambda _event: None),
        private_key=local_key,
        relays=local_relays,
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        outbox_store=outbox,
    )
    captured: dict[str, object] = {}

    async def fake_fetch(pubkey, lookup_relays, *, allowed_relay_urls, **_kwargs):
        assert pubkey == sender_pubkey
        assert lookup_relays == tuple(local_relays)
        assert allowed_relay_urls == tuple(local_relays)
        return ["wss://local-b.example", "wss://attacker.example"]

    async def fake_publish(
        events,
        relay_lists_by_pubkey,
        auth_private_key,
        *,
        allowed_relay_urls,
        **_kwargs,
    ):
        captured["events"] = events
        captured["routes"] = relay_lists_by_pubkey
        captured["key"] = auth_private_key
        captured["allowlist"] = allowed_relay_urls
        return [
            SimpleNamespace(event_id=str(index), accepted=True)
            for index, _ in enumerate(events)
        ]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)
    try:
        result = runtime.send_reply(
            {"sender_pubkey": sender_pubkey, "rumor_id": "cd" * 32},
            "Reply from UAG",
        )
        assert result["ok"] is True
        assert captured["routes"][sender_pubkey] == ["wss://local-b.example"]
        assert "wss://attacker.example" not in captured["allowlist"]
        assert len(captured["events"]) == 2
        assert all(event["kind"] == 1059 for event in captured["events"])
        record = outbox.get(sender_pubkey, "cd" * 32)
        assert record is not None
        assert record.status == "delivered"
        assert record.events is None
    finally:
        inbox.close()
        outbox.close()
        pairings.close()


def test_reply_outbox_retries_the_same_encrypted_event_ids(
    tmp_path, monkeypatch
) -> None:
    import asyncio
    import json

    from uagent import nostr_remote_transport as transport

    local_key = _secret(2)
    sender_key = _secret(1)
    sender_pubkey = _public_key(sender_key).hex()
    inbox = SQLiteNostrInboxStore(tmp_path / "retry-reply-inbox.sqlite3")
    outbox = SQLiteNostrOutboxStore(tmp_path / "retry-reply-outbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "retry-reply-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=100)
    runtime = NostrRemoteRuntime(
        event_queue=SimpleNamespace(put=lambda _event: None),
        private_key=local_key,
        relays=["wss://local.example"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        outbox_store=outbox,
    )
    published_ids: list[list[str]] = []

    async def fake_fetch(*_args, **_kwargs):
        return ["wss://local.example"]

    async def fake_publish(events, *_args, **_kwargs):
        published_ids.append([event["id"] for event in events])
        accepted = len(published_ids) > 1
        return [
            SimpleNamespace(event_id=event["id"], accepted=accepted) for event in events
        ]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", fake_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", fake_publish)
    request_id = "cd" * 32
    try:
        first_result = runtime.send_reply(
            {"sender_pubkey": sender_pubkey, "rumor_id": request_id},
            "Secret reply text",
        )
        assert first_result["queued"] is True
        pending = outbox.get(sender_pubkey, request_id)
        assert pending is not None
        assert pending.status == "pending"
        assert pending.events is not None
        assert "Secret reply text" not in json.dumps(pending.events)

        claimed = outbox.claim(sender_pubkey, request_id, now=pending.next_attempt_at)
        assert claimed is not None
        retry_result = asyncio.run(runtime._deliver_outbox_record(claimed))
        assert retry_result["state"] == "delivered"
        assert len(published_ids) == 2
        assert published_ids[0] == published_ids[1]
        delivered = outbox.get(sender_pubkey, request_id)
        assert delivered is not None
        assert delivered.status == "delivered"
        assert delivered.events is None
    finally:
        inbox.close()
        outbox.close()
        pairings.close()


def test_reply_is_persisted_before_transient_relay_list_lookup(
    tmp_path, monkeypatch
) -> None:
    import asyncio
    import json

    from uagent import nostr_remote_transport as transport

    local_key = _secret(2)
    sender_key = _secret(1)
    sender_pubkey = _public_key(sender_key).hex()
    inbox = SQLiteNostrInboxStore(tmp_path / "lookup-reply-inbox.sqlite3")
    outbox = SQLiteNostrOutboxStore(tmp_path / "lookup-reply-outbox.sqlite3")
    pairings = SQLitePairingStore(tmp_path / "lookup-reply-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=100)
    runtime = NostrRemoteRuntime(
        event_queue=SimpleNamespace(put=lambda _event: None),
        private_key=local_key,
        relays=["wss://local.example"],
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
        outbox_store=outbox,
    )
    fetch_calls = 0
    published_ids: list[list[str]] = []
    published_routes: list[dict[str, list[str]]] = []

    async def flaky_fetch(*_args, **_kwargs):
        nonlocal fetch_calls
        fetch_calls += 1
        if fetch_calls == 1:
            raise OSError("temporary relay lookup failure")
        return ["wss://local.example"]

    async def accept_publish(events, relay_lists_by_pubkey, *_args, **_kwargs):
        published_ids.append([event["id"] for event in events])
        published_routes.append(relay_lists_by_pubkey)
        return [
            SimpleNamespace(event_id=event["id"], accepted=True) for event in events
        ]

    monkeypatch.setattr(transport, "fetch_nip17_relay_list", flaky_fetch)
    monkeypatch.setattr(transport, "publish_nip17_gift_wraps", accept_publish)
    request_id = "ef" * 32
    try:
        result = runtime.send_reply(
            {"sender_pubkey": sender_pubkey, "rumor_id": request_id},
            "Persist this private reply",
        )
        assert result["queued"] is True
        pending = outbox.get(sender_pubkey, request_id)
        assert pending is not None
        assert pending.status == "pending"
        assert pending.events is not None
        assert sender_pubkey not in pending.relay_lists_by_pubkey
        assert "Persist this private reply" not in json.dumps(pending.events)

        claimed = outbox.claim(sender_pubkey, request_id, now=pending.next_attempt_at)
        assert claimed is not None
        retry_result = asyncio.run(runtime._deliver_outbox_record(claimed))
        assert retry_result["state"] == "delivered"
        assert fetch_calls == 2
        assert len(published_ids) == 1
        assert published_routes[0][sender_pubkey] == ["wss://local.example"]
        delivered = outbox.get(sender_pubkey, request_id)
        assert delivered is not None
        assert delivered.status == "delivered"
        assert delivered.events is None
        assert delivered.relay_lists_by_pubkey is None
    finally:
        inbox.close()
        outbox.close()
        pairings.close()
