from __future__ import annotations

from types import SimpleNamespace

from uagent.tools import cmd_exec_json_tool
from uagent.tools.cmd_exec_json_tool import (
    _command_output_encoding,
    _decode_process_output,
)


def test_windows_shell_commands_prefer_utf8_over_cp932_locale():
    assert (
        _command_output_encoding(
            "python -m black --check src",
            "cp932",
            is_windows=True,
        )
        == "utf-8"
    )


def test_direct_python_commands_keep_the_configured_encoding():
    assert (
        _command_output_encoding(
            "python -c 'print(1)'",
            "cp932",
            is_windows=True,
        )
        == "cp932"
    )


def test_utf8_subprocess_output_is_decoded_without_a_locale_codec():
    expected = "Black completed ✨"
    encoded = expected.encode("utf-8")

    assert _decode_process_output(encoded, "utf-8") == expected


def test_subprocess_output_uses_configured_legacy_encoding_when_valid():
    expected = "日本語の出力"
    encoded = expected.encode("cp932")

    assert _decode_process_output(encoded, "cp932") == expected


def test_cmd_runner_handles_real_black_unicode_output():
    result = cmd_exec_json_tool._run(
        "python -m black --check src/uagent/tools/cmd_exec_json_tool.py",
        cwd=None,
        timeout_ms=60_000,
    )

    assert result["returncode"] == 0, result["stderr"]
    assert result["ok"] is True


def test_cmd_runner_captures_bytes_and_decodes_after_communication(monkeypatch):
    expected = "Black completed ✨"
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=expected.encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(cmd_exec_json_tool.subprocess, "run", fake_run)
    result = cmd_exec_json_tool._run("echo test", cwd=None)

    assert "text" not in captured
    assert "encoding" not in captured
    assert result["stdout"] == expected
