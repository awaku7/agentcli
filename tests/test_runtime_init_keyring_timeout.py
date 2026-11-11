from __future__ import annotations

import os
import sys
import types

import pytest

from uagent.runtime import runtime_init


@pytest.mark.parametrize(
    ("configured_timeout", "expected_timeout"),
    [(None, "10"), ("17", "17")],
)
def test_load_dotenv_custom_uses_ten_second_keyring_timeout_by_default(
    monkeypatch, tmp_path, configured_timeout, expected_timeout
):
    monkeypatch.chdir(tmp_path)
    if configured_timeout is None:
        monkeypatch.delenv("UAGENT_KEYRING_TIMEOUT", raising=False)
    else:
        monkeypatch.setenv("UAGENT_KEYRING_TIMEOUT", configured_timeout)
    monkeypatch.delenv("UAGENT_TEST_KEYRING_TIMEOUT", raising=False)
    monkeypatch.setattr(runtime_init, "_STARTUP_UAGENT_ENV_SNAPSHOT", None)

    observed_timeouts: list[str | None] = []
    fake_envsec = types.ModuleType("uag_envsec")

    def migrate_key_file_to_keyring() -> bool:
        observed_timeouts.append(os.environ.get("UAGENT_KEYRING_TIMEOUT"))
        return False

    def decrypt_text(_body: str) -> str:
        observed_timeouts.append(os.environ.get("UAGENT_KEYRING_TIMEOUT"))
        return "UAGENT_TEST_KEYRING_TIMEOUT=loaded\n"

    fake_envsec.migrate_key_file_to_keyring = migrate_key_file_to_keyring
    fake_envsec.decrypt_text = decrypt_text
    monkeypatch.setitem(sys.modules, "uag_envsec", fake_envsec)
    (tmp_path / ".env.sec").write_text("encrypted\n", encoding="utf-8")

    runtime_init.load_dotenv_custom()

    assert observed_timeouts == [expected_timeout, expected_timeout]
    assert os.environ["UAGENT_TEST_KEYRING_TIMEOUT"] == "loaded"
