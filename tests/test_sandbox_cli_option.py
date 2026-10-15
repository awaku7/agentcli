from __future__ import annotations

import sys

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
