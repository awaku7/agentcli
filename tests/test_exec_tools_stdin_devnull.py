"""Ensure exec tools do not inherit host stdin."""

from __future__ import annotations

import json
import subprocess

import pytest


def test_bash_exec_uses_devnull_stdin(monkeypatch):
    import os
    from uagent.tools import bash_exec_tool as mod

    # The test intentionally exercises execution, including under the
    # non-interactive environment used by the test runner.
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "echo")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    if os.name == "nt":
        # Tool is disabled on Windows; still verify call site when forced available.
        monkeypatch.setattr(mod, "_TOOL_AVAILABLE", True)

    captured = {}

    class _P:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def fake_run(*a, **k):
        captured.update(k)
        return _P()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        mod,
        "decide_cmd_exec",
        lambda *a, **k: type(
            "D", (), {"allowed": True, "require_confirm": False, "reason": ""}
        )(),
    )
    monkeypatch.setattr(mod, "confirm_if_needed", lambda d: None)

    out = mod.run_tool({"command": "echo ok"})
    assert captured.get("stdin") is subprocess.DEVNULL
    assert "ok" in out


def test_bash_exec_blocks_non_interactive_without_explicit_opt_in(monkeypatch):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setattr(mod, "_TOOL_AVAILABLE", True)
    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.delenv("UAGENT_ALLOW_BASH_EXEC", raising=False)
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    out = mod.run_tool({"command": "echo should-not-run"})
    assert "[bash_exec" in out
    assert "UAGENT_ALLOW_BASH_EXEC=1" in out


def test_bash_exec_requires_allowlist_in_non_interactive_mode(monkeypatch):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setattr(mod, "_TOOL_AVAILABLE", True)
    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.delenv("UAGENT_BASH_EXEC_ALLOWLIST", raising=False)
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    out = mod.run_tool({"command": "echo should-not-run"})
    assert "[bash_exec" in out
    assert "UAGENT_BASH_EXEC_ALLOWLIST" in out


def test_bash_exec_rejects_command_outside_allowlist(monkeypatch):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setattr(mod, "_TOOL_AVAILABLE", True)
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "echo")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    out = mod.run_tool({"command": "python -V"})
    assert "[bash_exec" in out
    assert "not in UAGENT_BASH_EXEC_ALLOWLIST" in out


@pytest.mark.parametrize(
    "command",
    [
        "echo ok && uname",
        "echo ok; uname",
        "echo ok | uname",
    ],
)
def test_bash_exec_checks_every_command_against_allowlist(monkeypatch, command):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "echo")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    reason = mod._policy_block_reason(command)
    assert reason is not None
    assert "command 'uname'" in reason


@pytest.mark.parametrize(
    "command",
    [
        "echo $(uname)",
        "echo `uname`",
        "echo ok\nuname",
        "env PATH=/bin echo ok",
        "bash -lc 'uname'",
        "timeout 10 uname",
        "nice uname",
        "xargs uname",
    ],
)
def test_bash_exec_rejects_hidden_execution_in_allowlist_mode(monkeypatch, command):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "echo,env,bash")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    assert mod._policy_block_reason(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "git status && pytest -q",
        "printf ok | sed s/o/O/",
        "NAME=value echo ok; git status",
        "echo ok > result.txt",
        "echo ';'",
        'echo "a && b"',
        "echo '$(uname)'",
        "echo '`uname`'",
    ],
)
def test_bash_exec_allows_composition_when_every_command_is_allowlisted(
    monkeypatch, command
):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "echo,git,printf,pytest,sed")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    assert mod._policy_block_reason(command) is None


def test_bash_exec_policy_deny_overrides_explicit_opt_in(monkeypatch):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setattr(mod, "_TOOL_AVAILABLE", True)
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_POLICY", "deny")

    out = mod.run_tool({"command": "echo should-not-run"})
    assert "[bash_exec" in out
    assert "UAGENT_BASH_EXEC_POLICY" in out


def test_cmd_exec_json_uses_devnull_stdin(monkeypatch):
    from uagent.tools import cmd_exec_json_tool as mod

    captured = {}

    class _P:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def fake_run(*a, **k):
        captured.update(k)
        return _P()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        mod,
        "decide_cmd_exec",
        lambda *a, **k: type(
            "D", (), {"allowed": True, "require_confirm": False, "reason": ""}
        )(),
    )
    monkeypatch.setattr(mod, "confirm_if_needed", lambda d: None)

    out = mod.run_tool({"command": "echo ok"})
    assert captured.get("stdin") is subprocess.DEVNULL
    assert "ok" in out


def test_cmd_exec_json_converts_timeout_to_result(monkeypatch):
    from uagent.tools import cmd_exec_json_tool as mod
    from uagent.tools.context import ToolCallbacks, init_callbacks

    init_callbacks(ToolCallbacks(cmd_exec_timeout_ms=10, cmd_encoding="utf-8"))

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(
            k.get("args", "command"), k["timeout"], output=b"partial", stderr=b"err"
        )

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        mod,
        "decide_cmd_exec",
        lambda *a, **k: type(
            "D", (), {"allowed": True, "require_confirm": False, "reason": ""}
        )(),
    )
    monkeypatch.setattr(mod, "confirm_if_needed", lambda d: None)

    result = json.loads(mod.run_tool({"command": "sleep 1"}))
    assert result["timeout"] is True
    assert result["returncode"] == 124
    assert result["stdout"] == "partial"


def test_cmd_exec_json_converts_keyboard_interrupt_to_result(monkeypatch):
    from uagent.tools import cmd_exec_json_tool as mod

    def fake_run(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        mod,
        "decide_cmd_exec",
        lambda *a, **k: type(
            "D", (), {"allowed": True, "require_confirm": False, "reason": ""}
        )(),
    )
    monkeypatch.setattr(mod, "confirm_if_needed", lambda d: None)

    result = json.loads(mod.run_tool({"command": "echo ok"}))
    assert result["interrupted"] is True
    assert result["returncode"] == 130


def test_python_exec_uses_devnull_stdin(monkeypatch):
    from uagent.tools import python_exec_tool as mod
    from uagent.tools.context import ToolCallbacks, init_callbacks

    captured = {}

    class _P:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    def fake_run(*a, **k):
        captured.update(k)
        return _P()

    init_callbacks(
        ToolCallbacks(
            cmd_encoding="utf-8",
            python_exec_timeout_ms=5000,
            truncate_output=None,
        )
    )
    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    out = mod.run_tool({"code": "print('ok')"})
    assert captured.get("stdin") is subprocess.DEVNULL
    assert "ok" in out


def test_bash_exec_allowed_path_scope(monkeypatch, tmp_path):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "cat")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWED_PATHS", str(tmp_path))
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    reason = mod._policy_block_reason("cat /etc/passwd")
    assert reason is not None
    assert "outside UAGENT_BASH_EXEC_ALLOWED_PATHS" in reason


def test_bash_exec_allowed_host_scope(monkeypatch):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setenv("UAGENT_NON_INTERACTIVE", "1")
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "curl")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWED_HOSTS", "trusted.example")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)

    reason = mod._policy_block_reason("curl https://evil.example/data")
    assert reason is not None
    assert "outside UAGENT_BASH_EXEC_ALLOWED_HOSTS" in reason


def test_bash_exec_uses_bounded_timeout(monkeypatch):
    from uagent.tools import bash_exec_tool as mod

    monkeypatch.setattr(mod, "_TOOL_AVAILABLE", True)
    monkeypatch.setenv("UAGENT_ALLOW_BASH_EXEC", "1")
    monkeypatch.setenv("UAGENT_BASH_EXEC_ALLOWLIST", "echo")
    monkeypatch.setenv("UAGENT_BASH_EXEC_TIMEOUT_SEC", "7")
    monkeypatch.delenv("UAGENT_BASH_EXEC_POLICY", raising=False)
    monkeypatch.setattr(
        mod,
        "decide_cmd_exec",
        lambda *a, **k: type("D", (), {"allowed": True, "require_confirm": False})(),
    )
    monkeypatch.setattr(mod, "confirm_if_needed", lambda d: None)
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        raise mod.subprocess.TimeoutExpired(kwargs.get("args", "command"), 7)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    out = mod.run_tool({"command": "echo ok"})
    assert "timeout" in out
    assert captured["timeout"] == 7.0
