from __future__ import annotations

import time
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


def test_linux_defaults_to_file_backend(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_ENVSEC_KEY_BACKEND", raising=False)
    monkeypatch.setattr(secret_core.sys, "platform", "linux")

    assert secret_core._key_backend() == "file"


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


def test_auto_migrates_existing_file_key(monkeypatch, tmp_path: Path, capsys) -> None:
    fake = FakeKeyring()
    monkeypatch.setattr(secret_core, "_keyring_module", lambda: fake)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")
    monkeypatch.setattr(secret_core, "_home_dir", lambda: tmp_path)

    secret_core.ensure_key_file()
    old_key = (tmp_path / ".uag" / secret_core.DEFAULT_KEY_FILENAME).read_bytes()
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "auto")

    secret_core.ensure_key_file()
    assert "Migrated envsec key to OS keyring" in capsys.readouterr().err
    stored = fake.get_password(
        secret_core.KEYRING_SERVICE, secret_core.KEYRING_USERNAME
    )
    assert stored is not None
    assert secret_core._decode_key(stored) == old_key
    assert not (tmp_path / ".uag" / secret_core.DEFAULT_KEY_FILENAME).exists()


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


def test_auto_removes_duplicate_file_key_when_keyring_matches(
    monkeypatch, tmp_path: Path
) -> None:
    fake = FakeKeyring()
    monkeypatch.setattr(secret_core, "_keyring_module", lambda: fake)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")
    monkeypatch.setattr(secret_core, "_home_dir", lambda: tmp_path)

    secret_core.ensure_key_file()
    key_path = tmp_path / ".uag" / secret_core.DEFAULT_KEY_FILENAME
    key = key_path.read_bytes()
    fake.set_password(
        secret_core.KEYRING_SERVICE,
        secret_core.KEYRING_USERNAME,
        secret_core.base64.b64encode(key).decode("ascii"),
    )
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "auto")

    assert secret_core.ensure_key_file() == "keyring://uag-envsec/master-key"
    assert not key_path.exists()


def test_auto_replaces_different_keyring_key_with_file_key(
    monkeypatch, tmp_path: Path
) -> None:
    fake = FakeKeyring()
    monkeypatch.setattr(secret_core, "_keyring_module", lambda: fake)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "file")
    monkeypatch.setattr(secret_core, "_home_dir", lambda: tmp_path)

    secret_core.ensure_key_file()
    key_path = tmp_path / ".uag" / secret_core.DEFAULT_KEY_FILENAME
    file_key = key_path.read_bytes()
    fake.set_password(
        secret_core.KEYRING_SERVICE,
        secret_core.KEYRING_USERNAME,
        secret_core.base64.b64encode(b"x" * secret_core.MASTER_KEY_BYTES).decode(
            "ascii"
        ),
    )
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "auto")

    assert secret_core.ensure_key_file() == "keyring://uag-envsec/master-key"
    assert not key_path.exists()
    stored = fake.get_password(
        secret_core.KEYRING_SERVICE, secret_core.KEYRING_USERNAME
    )
    assert stored is not None
    assert secret_core._decode_key(stored) == file_key


def test_auto_falls_back_when_keyring_call_times_out(
    monkeypatch, tmp_path: Path
) -> None:
    class HangingKeyring:
        def get_password(self, service: str, username: str) -> None:
            time.sleep(1)
            return None

        def set_password(self, service: str, username: str, password: str) -> None:
            raise AssertionError("set_password must not be called after timeout")

    monkeypatch.setattr(secret_core, "_keyring_module", lambda: HangingKeyring())
    monkeypatch.setattr(secret_core, "_home_dir", lambda: tmp_path)
    monkeypatch.setattr(secret_core, "_KEYRING_TIMED_OUT", False)
    monkeypatch.setenv("UAGENT_ENVSEC_KEY_BACKEND", "auto")
    monkeypatch.setenv("UAGENT_KEYRING_TIMEOUT", "0.1")

    started = time.monotonic()
    location = secret_core.ensure_key_file()

    assert time.monotonic() - started < 0.8
    assert location == str(tmp_path / ".uag" / secret_core.DEFAULT_KEY_FILENAME)
    assert Path(location).exists()
