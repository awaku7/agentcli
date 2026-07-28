from __future__ import annotations

import json

from uagent.uagent_llm import (
    _MGMT_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
    check_mgmt_tool_loop,
    clear_mgmt_load_streak,
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


def test_parallel_load_different_tools_not_blocked() -> None:
    calls = [
        _tc("tool_load", name="file_grep"),
        _tc("tool_load", name="human_ask"),
        _tc("tool_load", name="delete_file"),
        _tc("tool_load", name="run_tests"),
    ]
    blocked, name, count = check_mgmt_tool_loop(calls)
    assert blocked is False
    assert name == ""
    assert count == 0
    # each target counted once
    assert _TOOL_CALL_FINGERPRINTS["tool_load:file_grep"] == 1
    assert _TOOL_CALL_FINGERPRINTS["tool_load:human_ask"] == 1
    assert _TOOL_CALL_FINGERPRINTS["tool_load:delete_file"] == 1
    assert _TOOL_CALL_FINGERPRINTS["tool_load:run_tests"] == 1


def test_same_target_repeated_is_blocked() -> None:
    for _ in range(_MGMT_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_mgmt_tool_loop([_tc("tool_load", name="file_grep")])
        assert blocked is False

    blocked, name, count = check_mgmt_tool_loop([_tc("tool_load", name="file_grep")])
    assert blocked is True
    assert name == "tool_load(file_grep)"
    assert count == _MGMT_LOOP_THRESHOLD


def test_same_round_same_target_four_times_blocked() -> None:
    calls = [_tc("tool_load", name="file_grep") for _ in range(_MGMT_LOOP_THRESHOLD)]
    blocked, name, count = check_mgmt_tool_loop(calls)
    assert blocked is True
    assert name == "tool_load(file_grep)"
    assert count == _MGMT_LOOP_THRESHOLD


def test_tool_catalog_different_queries_not_shared() -> None:
    blocked = False
    for _ in range(_MGMT_LOOP_THRESHOLD):
        blocked, _, _ = check_mgmt_tool_loop(
            [_tc("tool_catalog", query="search files")]
        )
        # first three ok, fourth blocks for this query
    assert blocked is True

    # different query starts fresh
    blocked2, _, count2 = check_mgmt_tool_loop([_tc("tool_catalog", query="run tests")])
    assert blocked2 is False
    assert count2 == 0


def test_unload_resets_load_counter_for_target() -> None:
    for _ in range(_MGMT_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
        assert blocked is False
    assert _TOOL_CALL_FINGERPRINTS["tool_load:read_file"] == _MGMT_LOOP_THRESHOLD - 1

    # unload clears the streak; next loads start from 1 again
    blocked, _, _ = check_mgmt_tool_loop([_tc("unload_tool", name="read_file")])
    assert blocked is False
    assert "tool_load:read_file" not in _TOOL_CALL_FINGERPRINTS

    for _ in range(_MGMT_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
        assert blocked is False
    assert _TOOL_CALL_FINGERPRINTS["tool_load:read_file"] == _MGMT_LOOP_THRESHOLD - 1

    blocked, name, count = check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
    assert blocked is True
    assert name == "tool_load(read_file)"
    assert count == _MGMT_LOOP_THRESHOLD


def test_unload_does_not_reset_other_targets() -> None:
    check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
    check_mgmt_tool_loop([_tc("tool_load", name="file_grep")])
    check_mgmt_tool_loop([_tc("unload_tool", name="read_file")])
    assert "tool_load:read_file" not in _TOOL_CALL_FINGERPRINTS
    assert _TOOL_CALL_FINGERPRINTS["tool_load:file_grep"] == 1


def test_unload_alone_is_not_loop_counted() -> None:
    for _ in range(_MGMT_LOOP_THRESHOLD + 2):
        blocked, name, count = check_mgmt_tool_loop(
            [_tc("unload_tool", name="read_file")]
        )
        assert blocked is False
        assert name == ""
        assert count == 0
    assert _TOOL_CALL_FINGERPRINTS == {}


def test_same_round_unload_then_load_starts_fresh() -> None:
    for _ in range(_MGMT_LOOP_THRESHOLD - 1):
        check_mgmt_tool_loop([_tc("tool_load", name="read_file")])

    # same round: unload resets before load is applied
    blocked, _, count = check_mgmt_tool_loop(
        [
            _tc("unload_tool", name="read_file"),
            _tc("tool_load", name="read_file"),
        ]
    )
    assert blocked is False
    assert count == 0
    assert _TOOL_CALL_FINGERPRINTS["tool_load:read_file"] == 1


def test_clear_mgmt_load_streak_helper() -> None:
    check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
    check_mgmt_tool_loop([_tc("tool_load", name="file_grep")])
    assert _TOOL_CALL_FINGERPRINTS["tool_load:read_file"] == 1
    clear_mgmt_load_streak("read_file")
    assert "tool_load:read_file" not in _TOOL_CALL_FINGERPRINTS
    assert _TOOL_CALL_FINGERPRINTS["tool_load:file_grep"] == 1


def test_disable_single_tool_clears_load_streak(monkeypatch) -> None:
    """Auto-unload path uses disable_single_tool, not unload_tool."""
    from uagent.tools import _genre_control_util as gcu

    check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
    check_mgmt_tool_loop([_tc("tool_load", name="file_grep")])
    assert _TOOL_CALL_FINGERPRINTS["tool_load:read_file"] == 1

    # Simulate a successful unload without needing a real registered tool.
    monkeypatch.setattr(gcu, "is_tool_pinned", lambda name: False)
    monkeypatch.setattr(gcu, "_LOADED_SINGLE_TOOLS", {"read_file": -1})
    monkeypatch.setattr(gcu, "_TOOL_DYNAMIC_THRESHOLDS", {"read_file": (5, 0, 1)})
    monkeypatch.setattr(gcu, "_PINNED_TOOLS", {})

    class _Spec:
        def __init__(self, name: str):
            self._name = name

        def get(self, key, default=None):
            if key == "function":
                return {"name": self._name}
            return default

    fake_specs = [_Spec("read_file"), _Spec("other")]
    fake_runners = {"read_file": object(), "other": object()}
    sorted_calls = []

    import uagent.tools as tools_pkg

    monkeypatch.setattr(tools_pkg, "TOOL_SPECS", fake_specs)
    monkeypatch.setattr(tools_pkg, "_RUNNERS", fake_runners)
    monkeypatch.setattr(
        tools_pkg, "_sort_registered_tools", lambda: sorted_calls.append(1)
    )

    ok = gcu.disable_single_tool("read_file")
    assert ok is True
    assert "tool_load:read_file" not in _TOOL_CALL_FINGERPRINTS
    assert _TOOL_CALL_FINGERPRINTS["tool_load:file_grep"] == 1
    # reload after auto-unload starts a fresh streak
    blocked, _, count = check_mgmt_tool_loop([_tc("tool_load", name="read_file")])
    assert blocked is False
    assert count == 0
    assert _TOOL_CALL_FINGERPRINTS["tool_load:read_file"] == 1
