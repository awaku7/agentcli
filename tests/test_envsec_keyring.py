from __future__ import annotations

from pathlib import Path

import pytest

import uag_envsec.secret_core as secret_core


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password


def test_keyring_backend_round_trip(monkeypatch, tmp_path: Path) -> None:
    fake = FakeKeyring()
    monkeypatch.setattr(secret_core, "_keyring_module", lambda: fake)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "keyring")
    monkeypatch.setattr(secret_core, "_home_dir", lambda: tmp_path)

    location = secret_core.ensure_key_file()
    assert location == "keyring://uag-envsec/master-key"
    assert not (tmp_path / ".uag" / secret_core.DEFAULT_KEY_FILENAME).exists()

    encrypted = secret_core.encrypt_text("UAGENT_TEST=value")
    assert secret_core.decrypt_text(encrypted) == "UAGENT_TEST=value"


def test_file_key_path_overrides_keyring(monkeypatch, tmp_path: Path) -> None:
    fake = FakeKeyring()
    monkeypatch.setattr(secret_core, "_keyring_module", lambda: fake)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "keyring")
    key_path = tmp_path / "explicit.key"

    secret_core.ensure_key_file(key_path)
    assert key_path.exists()
    assert secret_core.load_key(key_path) == key_path.read_bytes()


def test_keyring_backend_requires_keyring(monkeypatch) -> None:
    monkeypatch.setattr(secret_core, "_keyring_module", lambda: None)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "keyring")

    with pytest.raises(RuntimeError, match="python-keyring is not installed"):
        secret_core.ensure_key_file()
