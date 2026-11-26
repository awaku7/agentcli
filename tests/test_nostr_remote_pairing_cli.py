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
    devices_out = capsys.readouterr().out
    # Devices are shown by their npub, the form users recognize and
    # can paste back into pair/revoke, not by raw pubkey hex.
    assert nostr_transport.encode_npub(pubkey) in devices_out
    assert pubkey not in devices_out

    # Revoke accepts the npub form shown by :nostr devices.
    nostr_transport._cmd_nostr_revoke(nostr_transport.encode_npub(pubkey))
    with SQLitePairingStore(db_path) as store:
        assert not store.is_authorized(pubkey)
        assert store.list_devices() == []
        assert len(store.list_devices(include_revoked=True)) == 1

    assert "revoked" in capsys.readouterr().out


def test_bind_command_switches_chat_binding(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)
    registered = {spec["subcommand"] for spec in nostr_transport.CMD_SPECS}
    assert {"bind", "on", "off", "llm"} <= registered
    pubkey = _pubkey(124)

    nostr_transport._cmd_nostr_pair(f"{pubkey} My phone")
    capsys.readouterr()
    nostr_transport._cmd_nostr_bind(f"{pubkey} room")
    assert "room" in capsys.readouterr().out
    with SQLitePairingStore(db_path) as store:
        record = store.record_for(pubkey)
        assert record is not None and record.binding == "room"
    nostr_transport._cmd_nostr_devices("")
    assert "chat binding: room" in capsys.readouterr().out
    # The npub form works too, like revoke.
    nostr_transport._cmd_nostr_bind(f"{nostr_transport.encode_npub(pubkey)} attach")
    with SQLitePairingStore(db_path) as store:
        record = store.record_for(pubkey)
        assert record is not None and record.binding == "attach"
    nostr_transport._cmd_nostr_bind(pubkey)
    assert "Usage:" in capsys.readouterr().out
    nostr_transport._cmd_nostr_bind(f"{_pubkey(125)} room")
    assert "No active pairing" in capsys.readouterr().out


def test_mode_commands_switch_a_running_runtime(capsys) -> None:
    from types import SimpleNamespace

    modes: list[str] = []
    runtime = SimpleNamespace(
        mode="llm",
        set_mode=modes.append,
        status=lambda: {"state": "running"},
    )
    core = SimpleNamespace(_nostr_remote_runtime=runtime)
    nostr_transport._cmd_nostr_on("", core=core)
    assert modes == ["on"]
    assert "ON" in capsys.readouterr().out
    nostr_transport._cmd_nostr_llm("", core=core)
    assert modes == ["on", "llm"]
    assert "LLM" in capsys.readouterr().out


def test_mode_commands_restart_a_dead_listener(monkeypatch, capsys) -> None:
    from types import SimpleNamespace

    old_modes: list[str] = []
    dead = SimpleNamespace(
        mode="llm",
        set_mode=old_modes.append,
        status=lambda: {"state": "stopped"},
    )
    new_modes: list[str] = []
    fresh = SimpleNamespace(mode="llm", set_mode=new_modes.append)
    monkeypatch.setattr(
        nostr_transport, "_start_nostr_remote_for_command", lambda core: fresh
    )
    core = SimpleNamespace(_nostr_remote_runtime=dead)
    nostr_transport._cmd_nostr_llm("", core=core)
    # The dead runtime is recreated, not merely re-moded.
    assert old_modes == []
    assert new_modes == ["llm"]
    assert "LLM" in capsys.readouterr().out


def test_pairing_commands_reject_bad_usage(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)

    nostr_transport._cmd_nostr_pair("")
    assert "Usage:" in capsys.readouterr().out

    nostr_transport._cmd_nostr_revoke("bad key")
    assert "Usage:" in capsys.readouterr().out

    nostr_transport._cmd_nostr_devices("unknown")
    assert "Usage:" in capsys.readouterr().out


def test_llm_mode_start_requires_explicit_nostr_connection(monkeypatch, capsys) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(nostr_transport, "get_nostr_instance", lambda: None)
    nostr_transport._cmd_nostr_llm("", core=SimpleNamespace())
    assert "Run :nostr connect first" in capsys.readouterr().out


def test_remote_command_no_longer_starts_or_stops(capsys) -> None:
    from types import SimpleNamespace

    for operation in ("start", "stop"):
        nostr_transport._cmd_nostr_remote(operation, core=SimpleNamespace())
        assert "Usage: :nostr remote status|verify" in capsys.readouterr().out


def test_remote_status_prints_aggregate_receive_diagnostics(
    capsys, monkeypatch
) -> None:
    from types import SimpleNamespace

    import uagent.tools.i18n_helper as i18n_helper

    monkeypatch.setattr(i18n_helper, "detect_lang", lambda: "en")
    stats = {
        "state": "running",
        "pending": 0,
        "dispatching": 0,
        "error": "",
        "relays": ["wss://relay.example.org"],
        "diagnostics": {
            "connected_relays": 1,
            "gift_wraps": 2,
            "queued": 0,
            "invalid": 0,
            "decrypt_failed": 1,
            "unauthorized": 1,
            "stale": 0,
            "duplicate": 0,
            "inbox_rejected": 0,
        },
    }
    runtime = SimpleNamespace(status=lambda: stats)
    core = SimpleNamespace(_nostr_remote_runtime=runtime)
    nostr_transport._cmd_nostr_remote("status", core=core)
    output = capsys.readouterr().out
    assert "connected=1/1" in output
    assert "gift_wraps=2" in output
    assert "decrypt=1" in output
    assert "unpaired=1" in output
    assert "replies:" not in output  # legacy runtimes may lack outbox statistics


def test_remote_status_displays_reply_outbox_failure_category(capsys) -> None:
    from types import SimpleNamespace

    runtime = SimpleNamespace(
        status=lambda: {
            "state": "running",
            "pending": 0,
            "dispatching": 0,
            "relays": ["wss://relay.example"],
            "error": "",
            "outbox_summary": {
                "pending": 1,
                "sending": 0,
                "delivered": 0,
                "failed": 0,
                "last_error": "RecipientRelayListUnavailable",
            },
        }
    )
    nostr_transport._cmd_nostr_remote(
        "status", core=SimpleNamespace(_nostr_remote_runtime=runtime)
    )
    output = capsys.readouterr().out
    assert "replies: pending=1" in output
    assert "last_error=RecipientRelayListUnavailable" in output
