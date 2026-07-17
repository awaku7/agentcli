from __future__ import annotations

import json

from uagent.uagent_llm import (
    _MGMT_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
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
    for _ in range(_MGMT_LOOP_THRESHOLD):
        blocked, _, _ = check_mgmt_tool_loop(
            [_tc("tool_catalog", query="search files")]
        )
        # first three ok, fourth blocks for this query
    assert blocked is True

    # different query starts fresh
    blocked2, _, count2 = check_mgmt_tool_loop(
        [_tc("tool_catalog", query="run tests")]
    )
    assert blocked2 is False
    assert count2 == 0
