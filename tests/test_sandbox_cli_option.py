from __future__ import annotations

import sys

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
