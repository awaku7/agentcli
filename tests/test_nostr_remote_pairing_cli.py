from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import ec

from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent.tools import nostr_transport


def _pubkey(value: int) -> str:
    public_key = ec.derive_private_key(value, ec.SECP256K1()).public_key()
    return public_key.public_numbers().x.to_bytes(32, "big").hex()


def test_local_pairing_commands_pair_list_and_revoke(
    tmp_path, monkeypatch, capsys
) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)
    registered = {spec["subcommand"] for spec in nostr_transport.CMD_SPECS}
    assert {"pair", "revoke", "devices", "remote"} <= registered
    pubkey = _pubkey(123)

    nostr_transport._cmd_nostr_pair(f"{pubkey} My phone")
    with SQLitePairingStore(db_path) as store:
        assert store.is_authorized(pubkey)
        assert store.list_devices()[0].label == "My phone"

    nostr_transport._cmd_nostr_devices("")
    assert pubkey in capsys.readouterr().out

    nostr_transport._cmd_nostr_revoke(pubkey)
    with SQLitePairingStore(db_path) as store:
        assert not store.is_authorized(pubkey)
        assert store.list_devices() == []
        assert len(store.list_devices(include_revoked=True)) == 1

    assert "revoked" in capsys.readouterr().out


def test_pairing_commands_reject_bad_usage(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)

    nostr_transport._cmd_nostr_pair("")
    assert "Usage:" in capsys.readouterr().out

    nostr_transport._cmd_nostr_revoke("bad key")
    assert "Usage:" in capsys.readouterr().out

    nostr_transport._cmd_nostr_devices("unknown")
    assert "Usage:" in capsys.readouterr().out


def test_remote_listener_start_requires_explicit_nostr_connection(
    monkeypatch, capsys
) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(nostr_transport, "get_nostr_instance", lambda: None)
    nostr_transport._cmd_nostr_remote("start", core=SimpleNamespace())
    assert "Run :nostr connect first" in capsys.readouterr().out
