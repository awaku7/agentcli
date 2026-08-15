import sys

from uagent.util_common import parse_startup_args


def test_parse_startup_args_computer_use_enable(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["uag", "--computer-use"])
    args, unknown = parse_startup_args()
    assert args["computer_use"] is True
    assert unknown == []


def test_parse_startup_args_computer_use_disable(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["uag", "--no-computer-use"])
    args, unknown = parse_startup_args()
    assert args["computer_use"] is False
    assert unknown == []
