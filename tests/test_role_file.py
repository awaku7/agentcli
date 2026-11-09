import sys

import pytest

from uagent.cli_startup import _read_role_file
from uagent.util_common import parse_startup_args


def test_role_file_flag_is_parsed(monkeypatch, tmp_path):
    role_file = tmp_path / "role.txt"
    role_file.write_text("route batteries to a person", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["uag", "--embedded", "--role-file", str(role_file)])

    args, unknown = parse_startup_args()

    assert args["role_file"] == str(role_file)
    assert args["embedded"] is True
    assert unknown == []


def test_read_role_file_supports_relative_utf8_bom_path(tmp_path):
    role_file = tmp_path / "role.txt"
    role_file.write_bytes("\ufeff電池の指示".encode("utf-8"))

    assert _read_role_file("role.txt", base_dir=str(tmp_path)) == "電池の指示"


def test_read_role_file_fails_for_missing_or_empty_file(tmp_path):
    with pytest.raises(ValueError, match="cannot resolve"):
        _read_role_file("missing.txt", base_dir=str(tmp_path))

    empty = tmp_path / "empty.txt"
    empty.write_text(" \n", encoding="utf-8")
    with pytest.raises(ValueError, match="is empty"):
        _read_role_file(str(empty), base_dir=str(tmp_path))


def test_read_role_file_rejects_invalid_encoding_and_nul(tmp_path):
    invalid = tmp_path / "invalid.txt"
    invalid.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="not valid UTF-8"):
        _read_role_file(str(invalid), base_dir=str(tmp_path))

    nul = tmp_path / "nul.txt"
    nul.write_bytes(b"role\x00text")
    with pytest.raises(ValueError, match="NUL"):
        _read_role_file(str(nul), base_dir=str(tmp_path))


def test_read_role_file_enforces_size_limit(tmp_path, monkeypatch):
    import uagent.cli_startup as startup

    role_file = tmp_path / "large.txt"
    role_file.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(startup, "_ROLE_FILE_MAX_BYTES", 4)

    with pytest.raises(ValueError, match="exceeds the 4-byte limit"):
        _read_role_file(str(role_file), base_dir=str(tmp_path))


def test_initial_messages_put_role_before_unchanged_base_prompt(monkeypatch):
    from uagent.util_message import build_initial_messages

    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    logged = []

    class Core:
        SYSTEM_PROMPT = "built-in policies"

        @staticmethod
        def log_message(message):
            logged.append(message)

    messages = build_initial_messages(core=Core(), role_prompt="route batteries to a person")

    assert [message["role"] for message in messages[:2]] == ["system", "system"]
    assert "route batteries to a person" in messages[0]["content"]
    assert "built-in safety requirements" in messages[0]["content"]
    assert messages[1]["content"] == "built-in policies"
    assert logged[0] == messages[0]
    assert logged[1] == messages[1]
