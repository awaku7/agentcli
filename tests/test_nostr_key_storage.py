"""Tests for the Nostr key file storage in nostr_transport.

The key file must be stored encrypted (uag_envsec) with owner-only
permissions; legacy plaintext JSON files keep working and are migrated
to the encrypted form on first read.
"""

from __future__ import annotations

import json
import os

import pytest

from uagent.tools import nostr_transport as nt

_PRIV = "11" * 32
_PUB = "22" * 32


@pytest.fixture()
def key_env(tmp_path, monkeypatch):
    """Isolate HOME (envsec key material) and the Nostr key file path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    key_file = tmp_path / ".uag" / "bitchat" / "nostr_key.json"
    monkeypatch.setattr(nt, "_NOSTR_KEY_FILE", str(key_file))
    return key_file


def test_new_key_is_written_encrypted(key_env):
    priv, pub = nt._load_or_create_key()

    raw = key_env.read_text(encoding="utf-8")
    assert raw.startswith("uag-envsec:v1:")
    assert priv not in raw
    assert pub not in raw

    # A second load round-trips through the encrypted file.
    assert nt._load_or_create_key() == (priv, pub)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_new_key_file_has_owner_only_permissions(key_env):
    nt._load_or_create_key()
    assert key_env.stat().st_mode & 0o777 == 0o600


def test_legacy_plaintext_key_is_migrated(key_env):
    key_env.parent.mkdir(parents=True)
    key_env.write_text(
        json.dumps({"private_key": _PRIV, "public_key": _PUB}),
        encoding="utf-8",
    )

    assert nt._load_or_create_key() == (_PRIV, _PUB)

    raw = key_env.read_text(encoding="utf-8")
    assert raw.startswith("uag-envsec:v1:")
    assert _PRIV not in raw
    # The migrated file still loads to the same key pair.
    assert nt._load_or_create_key() == (_PRIV, _PUB)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions only")
def test_legacy_migration_tightens_permissions(key_env):
    key_env.parent.mkdir(parents=True)
    key_env.write_text(
        json.dumps({"private_key": _PRIV, "public_key": _PUB}),
        encoding="utf-8",
    )
    os.chmod(key_env, 0o644)

    nt._load_or_create_key()
    assert key_env.stat().st_mode & 0o777 == 0o600


def test_write_falls_back_to_plaintext_when_envsec_fails(key_env, monkeypatch):
    import uag_envsec

    def _boom(_text):
        raise RuntimeError("no crypto")

    monkeypatch.setattr(uag_envsec, "encrypt_text", _boom)

    priv, pub = nt._load_or_create_key()
    data = json.loads(key_env.read_text(encoding="utf-8"))
    assert data == {"private_key": priv, "public_key": pub}
    # The plaintext fallback still loads back.
    assert nt._load_or_create_key() == (priv, pub)


def test_corrupt_key_file_is_not_replaced(key_env):
    key_env.parent.mkdir(parents=True)
    key_env.write_text("not a key file", encoding="utf-8")
    before = key_env.read_bytes()

    with pytest.raises(nt.NostrKeyUnreadableError):
        nt._load_or_create_key()
    assert key_env.read_bytes() == before


def test_undecryptable_key_file_is_not_replaced(key_env, monkeypatch):
    import uag_envsec

    # Store a valid encrypted key, then simulate a locked backend.
    priv, pub = nt._load_or_create_key()
    before = key_env.read_bytes()

    def _boom(_text):
        raise RuntimeError("keyring locked")

    orig_decrypt = uag_envsec.decrypt_text
    monkeypatch.setattr(uag_envsec, "decrypt_text", _boom)

    with pytest.raises(nt.NostrKeyUnreadableError):
        nt._load_or_create_key()
    assert key_env.read_bytes() == before

    # Once the backend works again, the original identity is intact.
    monkeypatch.setattr(uag_envsec, "decrypt_text", orig_decrypt)
    assert nt._load_or_create_key() == (priv, pub)
