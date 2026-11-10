from __future__ import annotations

from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric import ec

from uagent.nostr_remote_inbox import SQLiteNostrInboxStore
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
    pairings = SQLitePairingStore(tmp_path / "reply-pairings.sqlite3")
    pairings.pair(sender_pubkey, "phone", approved=True, paired_at=100)
    runtime = NostrRemoteRuntime(
        event_queue=SimpleNamespace(put=lambda _event: None),
        private_key=local_key,
        relays=local_relays,
        session_id="active-session",
        inbox_store=inbox,
        pairing_store=pairings,
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
    finally:
        inbox.close()
        pairings.close()
