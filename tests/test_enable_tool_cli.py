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


def test_enable_tool_pins_requested_tools(monkeypatch):
    """Tools loaded via --enable-tool are pinned against auto-unload."""
    from uagent import tools as T
    from uagent.tools import _genre_control_util as G

    G._ENABLED_GENRES.clear()
    G._PINNED_TOOLS.clear()
    G._LOADED_SINGLE_TOOLS.clear()
    G._TOOL_DYNAMIC_THRESHOLDS.clear()
    with T._INIT_LOCK:
        T._INITIALIZED = False
        T.TOOL_SPECS.clear()
        T._RUNNERS.clear()
        T._TOOL_SPECS_CACHE = None
        T._TOOL_SPECS_DIRTY = True
        T._load_plugins()
        T._INITIALIZED = True

    from uagent.tools._genre_control_util import is_tool_pinned

    # Same enable-tool block as cli_startup.run_cli_startup(): load then pin.
    enable_tools = ["md2idx", "mk2idx"]
    for tname in reversed(enable_tools):
        ok = G.enable_single_tool(tname)
        assert ok is True, tname
        if ok:
            G.pin_tool(tname, reason="enabled via --enable-tool at startup")

    assert is_tool_pinned("md2idx") is True
    assert is_tool_pinned("mk2idx") is True
