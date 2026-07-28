from __future__ import annotations

import json

from uagent.uagent_llm import (
    _GENERAL_TOOL_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
    check_general_tool_loop,
    check_mgmt_tool_loop,
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


def test_general_tool_same_args_blocked_at_threshold() -> None:
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_windows_gps")])
        assert blocked is False

    blocked, name, count = check_general_tool_loop([_tc("get_windows_gps")])
    assert blocked is True
    assert name == "get_windows_gps"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD


def test_general_tool_different_args_not_shared() -> None:
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_weather_wttr", city="Tokyo")])
        assert blocked is False

    # Different args are a different fingerprint and reset the previous streak.
    blocked, _, _ = check_general_tool_loop([_tc("get_weather_wttr", city="Osaka")])
    assert blocked is False
    assert not any("Tokyo" in k for k in _TOOL_CALL_FINGERPRINTS)
    assert any("Osaka" in k for k in _TOOL_CALL_FINGERPRINTS)

    # Tokyo starts over from zero after the fingerprint change.
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_weather_wttr", city="Tokyo")])
        assert blocked is False
    blocked, name, count = check_general_tool_loop(
        [_tc("get_weather_wttr", city="Tokyo")]
    )
    assert blocked is True
    assert name == "get_weather_wttr"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD


def test_mgmt_tools_ignored_by_general_detector() -> None:
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD + 2):
        blocked, _, _ = check_general_tool_loop([_tc("tool_load", name="search_web")])
        assert blocked is False
    assert _TOOL_CALL_FINGERPRINTS == {}


def test_mgmt_and_general_detectors_coexist() -> None:
    for _ in range(3):
        check_mgmt_tool_loop([_tc("tool_load", name="search_web")])
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_windows_gps")])
        assert blocked is False
    blocked, name, count = check_general_tool_loop([_tc("get_windows_gps")])
    assert blocked is True
    assert name == "get_windows_gps"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD


def test_different_fingerprint_resets_other_counters() -> None:
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_windows_gps")])
        assert blocked is False
    assert any(k.startswith("tool:get_windows_gps:") for k in _TOOL_CALL_FINGERPRINTS)

    # Different fingerprint should drop the previous streak.
    blocked, _, _ = check_general_tool_loop(
        [_tc("get_weather_wttr", city="", lat=1.0, lon=2.0)]
    )
    assert blocked is False
    assert not any(
        k.startswith("tool:get_windows_gps:") for k in _TOOL_CALL_FINGERPRINTS
    )
    assert any(k.startswith("tool:get_weather_wttr:") for k in _TOOL_CALL_FINGERPRINTS)

    # Previous GPS streak must not carry over.
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_windows_gps")])
        assert blocked is False
    blocked, name, count = check_general_tool_loop([_tc("get_windows_gps")])
    assert blocked is True
    assert name == "get_windows_gps"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD
