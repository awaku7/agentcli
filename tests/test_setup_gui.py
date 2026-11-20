import builtins
import sys
from types import SimpleNamespace

import pytest

import scheck
from uagent import cli_entry, setup_cli, setup_gui


def test_build_minimal_config_keeps_only_selected_provider_and_other_settings():
    config = setup_gui.build_minimal_config(
        "openai",
        {
            "UAGENT_OPENAI_API_KEY": "openai-secret",
            "UAGENT_OPENAI_BASE_URL": "https://example.test/v1",
            "UAGENT_CLAUDE_API_KEY": "stale-secret",
        },
        {
            "UAGENT_PROVIDER": "claude",
            "UAGENT_CLAUDE_API_KEY": "old-secret",
            "UAGENT_LANG": "ja",
            "CUSTOM_SETTING": "keep",
        },
    )

    assert config == {
        "UAGENT_LANG": "ja",
        "CUSTOM_SETTING": "keep",
        "UAGENT_PROVIDER": "openai",
        "UAGENT_OPENAI_API_KEY": "openai-secret",
        "UAGENT_OPENAI_BASE_URL": "https://example.test/v1",
    }


def test_build_minimal_config_requires_provider_mandatory_values():
    with pytest.raises(ValueError, match="UAGENT_OPENAI_API_KEY"):
        setup_gui.build_minimal_config("openai", {})


def test_build_minimal_config_accepts_local_provider_required_url():
    config = setup_gui.build_minimal_config(
        "ollama", {"UAGENT_OLLAMA_BASE_URL": "http://localhost:11434/v1"}
    )

    assert config == {
        "UAGENT_PROVIDER": "ollama",
        "UAGENT_OLLAMA_BASE_URL": "http://localhost:11434/v1",
    }


def test_load_saved_config_merges_plain_and_encrypted_files(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "UAGENT_LANG=ja\nUAGENT_PROVIDER=openai\n", encoding="utf-8"
    )
    sec_path = tmp_path / f".env{setup_gui.DEFAULT_SEC_SUFFIX}"
    sec_path.write_text("ciphertext", encoding="utf-8")
    monkeypatch.setattr(
        setup_gui, "decrypt_text", lambda _text: "UAGENT_PROVIDER=ollama\n"
    )

    assert setup_gui.load_saved_config(tmp_path) == {
        "UAGENT_LANG": "ja",
        "UAGENT_PROVIDER": "ollama",
    }


def test_save_config_writes_plain_file_and_rejects_multiline_values(tmp_path):
    path = setup_gui.save_config(
        tmp_path,
        {"UAGENT_PROVIDER": "openai", "UAGENT_OPENAI_API_KEY": "secret"},
        encrypted=False,
    )

    assert path == tmp_path / ".env"
    assert "UAGENT_OPENAI_API_KEY=secret" in path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="single line"):
        setup_gui.serialize_config({"UAGENT_TEST": "first\nsecond"})


def test_uag_setup_dispatches_to_gui(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["uag", "setup"])
    monkeypatch.setattr(setup_gui, "main", lambda: 17)

    assert cli_entry.main() == 17


def test_uag_setup_cli_preserves_terminal_wizard(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["uag", "setup", "--cli"])
    monkeypatch.setattr(setup_cli, "main", lambda: 23)

    assert cli_entry.main() == 23


@pytest.mark.parametrize(
    ("args", "expected_module"),
    [([], "uagent.setup_gui"), (["--cli"], "uagent.setup_cli")],
)
def test_scheck_setup_dispatches_to_expected_wizard(monkeypatch, args, expected_module):
    monkeypatch.setattr(sys, "argv", ["scheck.py", "setup", *args])
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == expected_module:
            return SimpleNamespace(main=lambda: 0)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SystemExit) as exc_info:
        scheck.main()

    assert exc_info.value.code == 0
