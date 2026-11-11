from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from uagent.nostr_remote_dispatch import RemoteCLIRequestError, _parse_action
from uagent.nostr_remote_pairing import SQLitePairingStore
from uagent import nostr_setup
from uagent.tools import nostr_transport, qr_reader_tool


def _pubkey(value: int) -> str:
    public = ec.derive_private_key(value, ec.SECP256K1()).public_key()
    return public.public_numbers().x.to_bytes(32, "big").hex()


def test_pairing_qr_accepts_public_keys_only() -> None:
    key = _pubkey(7)
    npub = nostr_transport.encode_npub(key)
    assert nostr_setup.decode_pairing_pubkey(key.upper()) == key
    assert nostr_setup.decode_pairing_pubkey(npub) == key
    assert nostr_setup.decode_pairing_pubkey("nostr:" + npub) == key
    assert nostr_setup.decode_pairing_pubkey(npub.upper()) == key

    for invalid in (
        "nsec1" + npub[5:],
        "nostr:" + npub[:-1] + ("q" if npub[-1] != "q" else "p"),
        npub[:10].upper() + npub[10:],
        "https://example.com/" + npub,
        "nostr:" + "0" * 64,
        "{}",
        "A" * 200,
    ):
        with pytest.raises((ValueError, TypeError)):
            nostr_setup.decode_pairing_pubkey(invalid)


def test_reader_output_is_untrusted_until_validated(monkeypatch) -> None:
    key = _pubkey(9)
    npub = nostr_transport.encode_npub(key)
    monkeypatch.setattr(
        qr_reader_tool,
        "run_tool",
        lambda _args: json.dumps({"ok": True, "data": {"text": "nostr:" + npub}}),
    )
    assert nostr_setup.scan_mobile_pubkey() == key
    monkeypatch.setattr(
        qr_reader_tool,
        "run_tool",
        lambda _args: json.dumps({"ok": True, "data": {"cancelled": True}}),
    )
    assert nostr_setup.scan_mobile_pubkey() is None
    monkeypatch.setattr(
        qr_reader_tool,
        "run_tool",
        lambda _args: json.dumps({"ok": True, "data": {"text": "nsec1secret"}}),
    )
    with pytest.raises(ValueError):
        nostr_setup.scan_mobile_pubkey()


def test_setup_pairs_only_after_local_approval(tmp_path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    phone = _pubkey(11)
    pc = _pubkey(12)
    instance = SimpleNamespace(is_running=True, pubkey_hex=pc)
    calls = []
    monkeypatch.setattr(nostr_transport, "get_nostr_instance", lambda: instance)
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)
    monkeypatch.setattr(nostr_setup, "show_public_key_qr", lambda _npub: False)
    monkeypatch.setattr(nostr_setup, "scan_mobile_pubkey", lambda: phone)
    monkeypatch.setattr(nostr_setup, "confirm_local_pairing", lambda _key: True)
    monkeypatch.setattr(
        nostr_transport,
        "_cmd_nostr_remote",
        lambda arg, **kwargs: calls.append((arg, kwargs)),
    )

    core = SimpleNamespace(session_id="test")
    nostr_transport._cmd_nostr_setup("", core=core)
    with SQLitePairingStore(db_path) as store:
        assert store.is_authorized(phone)
    assert calls == [("start", {"core": core})]
    assert "experimental" in capsys.readouterr().out


def test_setup_decline_leaves_store_unchanged(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    phone = _pubkey(19)
    instance = SimpleNamespace(is_running=True, pubkey_hex=_pubkey(20))
    monkeypatch.setattr(nostr_transport, "get_nostr_instance", lambda: instance)
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)
    monkeypatch.setattr(nostr_setup, "show_public_key_qr", lambda _npub: True)
    monkeypatch.setattr(nostr_setup, "scan_mobile_pubkey", lambda: phone)
    monkeypatch.setattr(nostr_setup, "confirm_local_pairing", lambda _key: False)
    nostr_transport._cmd_nostr_setup("", core=SimpleNamespace(session_id="test"))
    assert not db_path.exists()


def test_pair_command_supports_npub(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "pairings.sqlite3"
    monkeypatch.setattr(nostr_transport, "_pairing_database_path", lambda: db_path)
    phone = _pubkey(25)
    nostr_transport._cmd_nostr_pair(nostr_transport.encode_npub(phone) + " Phone")
    with SQLitePairingStore(db_path) as store:
        assert store.is_authorized(phone)


@pytest.mark.parametrize(
    "command",
    ["/uag cmd :nostr setup", "/uag cmd :nostr:setup", "/uag cmd ::nostr setup"],
)
def test_remote_setup_command_is_rejected(command: str) -> None:
    with pytest.raises(RemoteCLIRequestError, match="local-only"):
        _parse_action(command)


def test_pairing_confirmation_uses_translated_text_and_public_npub(monkeypatch) -> None:
    import sys
    from types import ModuleType

    phone = _pubkey(31)
    npub = nostr_transport.encode_npub(phone)
    translated = []
    dialogs = []
    root_actions = []

    tkinter = ModuleType("tkinter")
    messagebox = ModuleType("tkinter.messagebox")
    root = SimpleNamespace(
        withdraw=lambda: root_actions.append("withdraw"),
        destroy=lambda: root_actions.append("destroy"),
    )
    tkinter.Tk = lambda: root
    tkinter.messagebox = messagebox

    def askyesno(title, message, *, parent):
        dialogs.append((title, message, parent))
        return True

    messagebox.askyesno = askyesno

    def translate(message):
        translated.append(message)
        return "[translated] " + message

    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", messagebox)
    monkeypatch.setattr(nostr_setup, "_", translate)

    assert nostr_setup.confirm_local_pairing(phone) is True
    assert len(translated) == 2
    assert "%(pubkey)s" in translated[1]
    assert dialogs == [
        (
            "[translated] UAG Nostr remote pairing",
            "[translated] " + translated[1].replace("%(pubkey)s", npub),
            root,
        )
    ]
    assert root_actions == ["withdraw", "destroy"]


def test_pairing_confirmation_fails_closed_if_dialog_unavailable(monkeypatch) -> None:
    import sys
    from types import ModuleType

    tkinter = ModuleType("tkinter")

    def unavailable():
        raise RuntimeError("no local display")

    tkinter.Tk = unavailable
    tkinter.messagebox = ModuleType("tkinter.messagebox")
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", tkinter.messagebox)
    assert nostr_setup.confirm_local_pairing(_pubkey(32)) is False
