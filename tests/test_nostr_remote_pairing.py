from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from uagent.nostr_remote_dispatch import (
    RemoteCLIRequestError,
    authorize_nostr_remote_request,
)
from uagent.nostr_remote_pairing import SQLitePairingStore


def _pubkey(value: int) -> str:
    public_key = ec.derive_private_key(value, ec.SECP256K1()).public_key()
    return public_key.public_numbers().x.to_bytes(32, "big").hex()


def test_pairing_requires_explicit_local_approval(tmp_path) -> None:
    path = tmp_path / "remote-pairings.sqlite3"
    with SQLitePairingStore(path) as store:
        with pytest.raises(PermissionError, match="local operator approval"):
            store.pair(_pubkey(1), "phone", approved=False, paired_at=100)
        assert store.list_devices(include_revoked=True) == []

        record = store.pair(
            _pubkey(1).upper(), "my phone", approved=True, paired_at=101
        )
        assert record.pubkey == _pubkey(1)
        assert record.label == "my phone"
        assert record.paired_at == 101
        assert record.revoked_at is None
        assert record.active
        assert store.is_authorized(_pubkey(1).upper())


def test_revocation_is_immediate_idempotent_and_persistent(tmp_path) -> None:
    path = tmp_path / "remote-pairings-revoke.sqlite3"
    key = _pubkey(2)
    with SQLitePairingStore(path) as store:
        store.pair(key, "tablet", approved=True, paired_at=100)
        assert store.revoke(key, revoked_at=200)
        assert not store.is_authorized(key)
        assert not store.revoke(key, revoked_at=201)
        assert store.list_devices() == []
        revoked = store.list_devices(include_revoked=True)
        assert len(revoked) == 1
        assert revoked[0].revoked_at == 200

    with SQLitePairingStore(path) as reopened:
        assert not reopened.is_authorized(key)
        assert reopened.list_devices(include_revoked=True) == revoked


def test_dispatcher_callback_observes_revocation_for_queued_request(tmp_path) -> None:
    key = _pubkey(8)
    queued_event = {
        "kind": "nostr_remote_request",
        "sender_pubkey": key,
        "rumor_id": _pubkey(9),
        "created_at": 1_700_000_000,
        "session_id": "active-session",
        "text": "hello",
    }
    with SQLitePairingStore(tmp_path / "remote-pairings-dispatch.sqlite3") as store:
        store.pair(key, "phone", approved=True, paired_at=1_699_999_000)
        action = authorize_nostr_remote_request(
            queued_event,
            current_session_id="active-session",
            authorize_sender=store.is_authorized,
            now=1_700_000_000,
        )
        assert action.kind == "user"

        store.revoke(key, revoked_at=1_700_000_001)
        with pytest.raises(RemoteCLIRequestError, match="not paired"):
            authorize_nostr_remote_request(
                queued_event,
                current_session_id="active-session",
                authorize_sender=store.is_authorized,
                now=1_700_000_002,
            )


def test_repair_requires_new_explicit_approval_and_resets_revocation(tmp_path) -> None:
    key = _pubkey(3)
    with SQLitePairingStore(tmp_path / "remote-pairings-repair.sqlite3") as store:
        store.pair(key, "old label", approved=True, paired_at=100)
        store.revoke(key, revoked_at=200)
        with pytest.raises(PermissionError):
            store.pair(key, "new label", approved=False, paired_at=300)
        assert not store.is_authorized(key)

        record = store.pair(key, "new label", approved=True, paired_at=301)
        assert record.active
        assert record.paired_at == 301
        assert record.revoked_at is None
        assert record.label == "new label"
        assert store.is_authorized(key)
        assert len(store.list_devices(include_revoked=True)) == 1


def test_unknown_malformed_or_revoked_keys_fail_closed(tmp_path) -> None:
    with SQLitePairingStore(tmp_path / "remote-pairings-fail-closed.sqlite3") as store:
        assert not store.is_authorized(_pubkey(4))
        assert not store.is_authorized("not-a-key")
        assert not store.is_authorized("ff" * 33)
        assert not store.is_authorized("ff" * 32)
        with pytest.raises(ValueError):
            store.pair("not-a-key", approved=True, paired_at=100)
        with pytest.raises(ValueError, match="secp256k1"):
            store.pair("ff" * 32, approved=True, paired_at=100)
        key = _pubkey(5)
        store.pair(key, approved=True, paired_at=100)
        assert store.revoke(key, revoked_at=101)
        assert not store.is_authorized(key)


@pytest.mark.parametrize(
    "label",
    [
        "x" * 129,
        "界" * 43,
        "bad\x00label",
        "line\nbreak",
        "\x1b[31mred",
        "\ud800",
    ],
)
def test_pairing_rejects_unsafe_or_oversized_labels(tmp_path, label: str) -> None:
    with SQLitePairingStore(tmp_path / "remote-pairings-label.sqlite3") as store:
        with pytest.raises(ValueError):
            store.pair(_pubkey(6), label, approved=True, paired_at=100)
        assert store.list_devices(include_revoked=True) == []


def test_pairing_rejects_invalid_timestamps_and_list_options(tmp_path) -> None:
    with SQLitePairingStore(tmp_path / "remote-pairings-values.sqlite3") as store:
        for timestamp in (True, -1):
            with pytest.raises(ValueError):
                store.pair(_pubkey(7), approved=True, paired_at=timestamp)
            with pytest.raises(ValueError):
                store.revoke(_pubkey(7), revoked_at=timestamp)
        with pytest.raises(TypeError):
            store.list_devices(include_revoked=1)
