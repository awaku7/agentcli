"""Ensure exec tools do not inherit host stdin."""
from __future__ import annotations

import subprocess


def test_bash_exec_uses_devnull_stdin(monkeypatch):
    import os
    from uagent.tools import bash_exec_tool as mod

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
