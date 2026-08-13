from __future__ import annotations

from uagent.tools import format_tool_names_for_log
from uagent.tools import _tool_load_order_key


def _spec(name: str, load_order=None, single_seq=None) -> dict:
    spec = {
        "type": "function",
        "function": {"name": name, "parameters": {"type": "object"}},
    }
    if load_order is not None:
        spec["load_order"] = load_order
    if single_seq is not None:
        spec["x_single_load_seq"] = single_seq
    return spec


def test_single_load_sorts_before_static_minus_one() -> None:
    specs = [
        _spec("read_file", load_order=-1),
        _spec("list_dir", load_order=-1),
        _spec("core_tool"),  # missing load_order
        _spec("search_web", single_seq=-2),  # newer single-load
        _spec("get_weather_wttr", single_seq=-1),  # older single-load
        _spec("explicit", load_order=10),
    ]
    ordered = sorted(specs, key=_tool_load_order_key)
    names = [s["function"]["name"] for s in ordered]
    assert names == [
        "search_web",
        "get_weather_wttr",
        "list_dir",
        "read_file",
        "core_tool",
        "explicit",
    ]


def test_static_minus_one_still_before_missing_and_positive() -> None:
    specs = [
        _spec("explicit", load_order=5),
        _spec("missing"),
        _spec("apply_patch", load_order=-1),
    ]
    ordered = sorted(specs, key=_tool_load_order_key)
    names = [s["function"]["name"] for s in ordered]
    assert names == ["apply_patch", "missing", "explicit"]


def test_format_tool_names_preserves_order() -> None:
    specs = [
        {"type": "web_search"},
        {"type": "function", "name": "search_web", "description": "", "parameters": {}},
        {
            "type": "function",
            "function": {"name": "get_current_location", "parameters": {"type": "object"}},
        },
    ]
    assert format_tool_names_for_log(specs) == [
        "web_search",
        "search_web",
        "get_current_location",
    ]
