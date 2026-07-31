from __future__ import annotations

import json

from uagent.uagent_llm import (
    _GENERAL_TOOL_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
    check_general_tool_loop,
    clear_general_tool_loop_streaks,
    _tool_calls_include_name,
)


def _tc(tool_name: str, **args) -> dict:
    return {
        "function": {
            "name": tool_name,
            "arguments": json.dumps(args, ensure_ascii=False),
        }
    }


def setup_function() -> None:
    _TOOL_CALL_FINGERPRINTS.clear()


def test_tool_calls_include_name() -> None:
    assert _tool_calls_include_name([_tc("tool_catalog", query="news")], "tool_catalog")
    assert not _tool_calls_include_name([_tc("tool_load", name="x")], "tool_catalog")


def test_clear_general_tool_loop_streaks_keeps_mgmt() -> None:
    _TOOL_CALL_FINGERPRINTS["tool:get_windows_gps:{}"] = 3
    _TOOL_CALL_FINGERPRINTS["tool_load:search_web"] = 2
    _TOOL_CALL_FINGERPRINTS["tool_catalog:query=news:all=False"] = 1
    clear_general_tool_loop_streaks()
    assert "tool:get_windows_gps:{}" not in _TOOL_CALL_FINGERPRINTS
    assert _TOOL_CALL_FINGERPRINTS["tool_load:search_web"] == 2
    assert _TOOL_CALL_FINGERPRINTS["tool_catalog:query=news:all=False"] == 1


def test_catalog_boundary_allows_fresh_general_streak() -> None:
    # Build up a near-threshold general streak.
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_windows_gps")])
        assert blocked is False

    # Re-planning boundary.
    clear_general_tool_loop_streaks()

    # Same tool can start over without immediately tripping.
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, count = check_general_tool_loop([_tc("get_windows_gps")])
        assert blocked is False
    blocked, name, count = check_general_tool_loop([_tc("get_windows_gps")])
    assert blocked is True
    assert name == "get_windows_gps"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD
