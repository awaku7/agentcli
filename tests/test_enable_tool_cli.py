import sys

from uagent.util_common import parse_startup_args


def _parse(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["uag"] + argv)
    args, _unknown = parse_startup_args()
    return args


def test_enable_tool_single(monkeypatch):
    args = _parse(monkeypatch, ["--enable-tool", "md2idx"])
    assert args["enable_tools"] == ["md2idx"]


def test_enable_tool_repeated_flags(monkeypatch):
    args = _parse(monkeypatch, ["--enable-tool", "md2idx", "--enable-tool", "mk2idx"])
    assert args["enable_tools"] == ["md2idx", "mk2idx"]


def test_enable_tool_comma_separated(monkeypatch):
    args = _parse(monkeypatch, ["--enable-tool", "md2idx,mk2idx"])
    assert args["enable_tools"] == ["md2idx", "mk2idx"]


def test_enable_tool_mixed_order_preserved(monkeypatch):
    args = _parse(
        monkeypatch,
        ["--enable-tool", "a", "--enable-tool", "b,c", "--enable-tool", " d , e "],
    )
    assert args["enable_tools"] == ["a", "b", "c", "d", "e"]


def test_enable_tool_empty_parts_ignored(monkeypatch):
    args = _parse(monkeypatch, ["--enable-tool", "a,,b,"])
    assert args["enable_tools"] == ["a", "b"]


def test_enable_tool_not_specified(monkeypatch):
    args = _parse(monkeypatch, [])
    assert args["enable_tools"] is None
