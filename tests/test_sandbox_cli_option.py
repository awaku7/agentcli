from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from uagent.util_common import parse_startup_args


def test_cli_sandbox_option_values_are_parsed(monkeypatch):
    for value in ("off", "auto", "mxc"):
        monkeypatch.setattr(sys, "argv", ["uag", "--sandbox", value])
        args, unknown = parse_startup_args()
        assert args["sandbox"] == value
        assert unknown == []


def test_cli_sandbox_option_defaults_to_unspecified(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["uag"])
    args, _unknown = parse_startup_args()
    assert args["sandbox"] is None


def test_cli_sandbox_mode_can_be_resolved_after_dotenv_loading(monkeypatch):
    from uagent.cli_impl import startup

    monkeypatch.setattr(startup, "UAGENT_SANDBOX_ARG", None)
    monkeypatch.setenv("UAGENT_SANDBOX_MODE", "mxc")
    assert startup.resolve_sandbox_mode() == "mxc"

    monkeypatch.setattr(startup, "UAGENT_SANDBOX_ARG", "off")
    assert startup.resolve_sandbox_mode() == "off"


def test_shared_sandbox_mode_resolution_uses_cli_precedence_and_validates_values():
    from uagent.runtime.sandbox_config import resolve_sandbox_mode

    assert resolve_sandbox_mode(None, "mxc") == "mxc"
    assert resolve_sandbox_mode("off", "mxc") == "off"
    with pytest.raises(ValueError, match="UAGENT_SANDBOX_MODE"):
        resolve_sandbox_mode(None, "typo")


def test_cli_startup_import_defers_invalid_sandbox_env_validation():
    repo_root = Path(__file__).parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root / "src"), env.get("PYTHONPATH", "")]
    )
    env["UAGENT_SANDBOX_MODE"] = "invalid-mode"

    result = subprocess.run(
        [sys.executable, "-c", "import uagent.cli_impl.startup"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_sandbox_cli_commands_never_load_dynamic_host_tools(monkeypatch, capsys):
    from types import SimpleNamespace

    from uagent import tools
    from uagent.util_tools import handle_command

    def forbidden(*_args, **_kwargs):
        raise AssertionError(
            "Dynamic host command loading is forbidden in Sandbox mode"
        )

    monkeypatch.setattr(tools, "_ensure_loaded", forbidden)
    monkeypatch.setattr(tools, "handle_dynamic_command", forbidden)
    core = SimpleNamespace(
        _sandbox_enabled=True,
        tools_enabled=True,
        tr=lambda message, **_kwargs: message,
    )

    assert handle_command(":help", [], None, "", core=core) is True
    help_text = capsys.readouterr().out
    assert "Sandbox-safe commands" in help_text
    assert "Dynamic commands" not in help_text

    result = handle_command(":tools list", [], None, "", core=core)
    assert result
    assert "unavailable in Sandbox mode" in capsys.readouterr().out

    handle_command(":tools off", [], None, "", core=core)
    assert core.tools_enabled is False


def test_sandbox_scheduled_callbacks_never_load_host_tools(monkeypatch):
    from uagent import tools
    from uagent.scheduler import tool_guard
    from uagent.scheduler.tool_guard import run_scheduled_callback_with_tools

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Host tool loading is forbidden in Sandbox mode")

    monkeypatch.setattr(tool_guard, "required_tools_guard", forbidden)
    monkeypatch.setattr(tools, "_ensure_loaded", forbidden)

    result = run_scheduled_callback_with_tools(
        lambda value: f"ran:{value}",
        "safe",
        tool_names=["python_exec"],
        reason="test sandbox run",
        sandbox_enabled=True,
    )
    assert result == "ran:safe"

    with pytest.raises(RuntimeError, match="unavailable Host tool"):
        run_scheduled_callback_with_tools(
            lambda: "must not run",
            tool_names=["excel_ops"],
            reason="test sandbox run",
            sandbox_enabled=True,
        )


def test_non_sandbox_scheduled_callback_still_uses_required_tools_guard(monkeypatch):
    from contextlib import contextmanager

    from uagent.scheduler import tool_guard
    from uagent.scheduler.tool_guard import run_scheduled_callback_with_tools

    observed = []

    @contextmanager
    def fake_guard(names, *, reason):
        observed.append((names, reason))
        yield names

    monkeypatch.setattr(tool_guard, "required_tools_guard", fake_guard)

    result = run_scheduled_callback_with_tools(
        lambda value: value.upper(),
        "scheduled",
        tool_names=["excel_ops"],
        reason="scheduled run:test",
        sandbox_enabled=False,
    )

    assert result == "SCHEDULED"
    assert observed == [(("excel_ops",), "scheduled run:test")]


def test_realtime_sandbox_mode_is_resolved_after_workdir_dotenv(monkeypatch):
    from uagent.cli_impl import main as cli_main
    from uagent.runtime import runtime_init

    events = []
    decision = object()
    monkeypatch.setattr(
        runtime_init,
        "decide_workdir",
        lambda **_kwargs: events.append("decide") or decision,
    )
    monkeypatch.setattr(
        runtime_init,
        "apply_workdir",
        lambda selected: events.append(("apply", selected is decision)),
    )
    monkeypatch.setattr(
        runtime_init,
        "reload_dotenv_custom",
        lambda: events.append("dotenv"),
    )
    monkeypatch.setattr(
        cli_main,
        "resolve_sandbox_mode",
        lambda: events.append("resolve") or "mxc",
    )

    assert cli_main._resolve_realtime_sandbox_mode() == "mxc"
    assert events == ["decide", ("apply", True), "dotenv", "resolve"]


def test_realtime_cli_rejects_invalid_sandbox_configuration(monkeypatch, capsys):
    from uagent.cli_impl import main as cli_main
    from uagent.runtime import logging_setup

    class StdoutStub:
        @staticmethod
        def reconfigure(**_kwargs):
            return None

    def invalid_mode():
        raise ValueError("invalid sandbox mode")

    monkeypatch.setattr(cli_main, "UAGENT_REALTIME", True)
    monkeypatch.setattr(cli_main, "_resolve_realtime_sandbox_mode", invalid_mode)
    monkeypatch.setattr(cli_main, "configure_event_logging", lambda: None)
    monkeypatch.setattr(logging_setup, "bind_event_context", lambda **_kwargs: None)
    monkeypatch.setattr(cli_main, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main.sys, "stdout", StdoutStub())

    assert cli_main.main() == 2
    assert "invalid configuration" in capsys.readouterr().err


def test_realtime_cli_rejects_sandbox_before_running_realtime(monkeypatch, capsys):
    from uagent.cli_impl import main as cli_main
    from uagent.runtime import logging_setup

    class StdoutStub:
        @staticmethod
        def reconfigure(**_kwargs):
            return None

    monkeypatch.setattr(cli_main, "UAGENT_REALTIME", True)
    monkeypatch.setattr(cli_main, "_resolve_realtime_sandbox_mode", lambda: "mxc")
    monkeypatch.setattr(cli_main, "configure_event_logging", lambda: None)
    monkeypatch.setattr(logging_setup, "bind_event_context", lambda **_kwargs: None)
    monkeypatch.setattr(cli_main, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_main.sys, "stdout", StdoutStub())

    assert cli_main.main() == 2
    assert "realtime mode is unavailable" in capsys.readouterr().err
