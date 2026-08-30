from __future__ import annotations

from uagent.scheduler.tool_guard import required_tools_guard


def test_required_tools_guard_pins_visible_tool_and_restores_state(monkeypatch):
    import uagent.tools as tools
    import uagent.tools._genre_control_util as genre

    pins = {}
    monkeypatch.setattr(
        tools, "get_tool_specs", lambda: [{"function": {"name": "excel_ops"}}]
    )
    monkeypatch.setattr(genre, "list_pinned_tools", lambda: dict(pins))
    monkeypatch.setattr(genre, "is_tool_pinned", lambda name: name in pins)
    monkeypatch.setattr(
        genre,
        "pin_tool",
        lambda name, reason="": pins.__setitem__(name, reason) or True,
    )
    monkeypatch.setattr(
        genre, "unpin_tool", lambda name: pins.pop(name, None) is not None
    )

    with required_tools_guard(["excel_ops"], reason="test") as names:
        assert names == ("excel_ops",)
        assert "excel_ops" in pins

    assert pins == {}


def test_required_tools_guard_loads_and_unloads_missing_tool(monkeypatch):
    import uagent.tools as tools
    import uagent.tools._genre_control_util as genre

    pins = {}
    calls = []
    monkeypatch.setattr(tools, "get_tool_specs", lambda: [])
    monkeypatch.setattr(genre, "list_pinned_tools", lambda: dict(pins))
    monkeypatch.setattr(genre, "is_tool_pinned", lambda name: name in pins)
    monkeypatch.setattr(
        genre,
        "pin_tool",
        lambda name, reason="": pins.__setitem__(name, reason) or True,
    )
    monkeypatch.setattr(
        genre, "unpin_tool", lambda name: pins.pop(name, None) is not None
    )
    monkeypatch.setattr(
        genre, "enable_single_tool", lambda name: calls.append(("enable", name)) or True
    )
    monkeypatch.setattr(
        genre,
        "disable_single_tool",
        lambda name: calls.append(("disable", name)) or True,
    )

    with required_tools_guard(["excel_ops"]):
        assert "excel_ops" in pins

    assert calls == [("enable", "excel_ops"), ("disable", "excel_ops")]
    assert pins == {}
