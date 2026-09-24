from __future__ import annotations

import json

from uagent.i18n import set_thread_lang
from uagent.uagent_llm import (
    _GENERAL_TOOL_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
    check_consecutive_tool_calls,
    clear_consecutive_tool_call_streak,
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
    set_thread_lang("en")
    _TOOL_CALL_FINGERPRINTS.clear()
    clear_consecutive_tool_call_streak()


def test_consecutive_tool_rounds_count_across_tool_names() -> None:
    names = ("add_long_memory", "search_web", "read_file")
    for index, tool_name in enumerate(names, start=1):
        blocked, name, count = check_consecutive_tool_calls(
            [_tc(tool_name, sample=index)], threshold=4
        )
        assert blocked is False
        assert name == "consecutive tool calls"
        assert count == index

    blocked, name, count = check_consecutive_tool_calls(
        [_tc("list_dir", path=".")], threshold=4
    )
    assert blocked is True
    assert name == "consecutive tool calls"
    assert count == 4


def test_invalid_consecutive_limit_uses_documented_default(monkeypatch) -> None:
    monkeypatch.setattr("uagent.uagent_llm.env_get", lambda *_args: "invalid")

    for _ in range(49):
        blocked, _, _ = check_consecutive_tool_calls([_tc("read_file")])
        assert blocked is False

    blocked, _, count = check_consecutive_tool_calls([_tc("search_web")])
    assert blocked is True
    assert count == 50


def test_parallel_same_tool_calls_count_as_one_round() -> None:
    calls = [_tc("read_file", filename=f"file-{i}.py") for i in range(5)]

    blocked, name, count = check_consecutive_tool_calls(calls, threshold=3)
    assert blocked is False
    assert name == "consecutive tool calls"
    assert count == 1

    blocked, _, count = check_consecutive_tool_calls(
        [
            _tc("read_file", filename="next-a.py"),
            _tc("read_file", filename="next-b.py"),
        ],
        threshold=3,
    )
    assert blocked is False
    assert count == 2

    blocked, name, count = check_consecutive_tool_calls(
        [_tc("read_file", filename="third.py")], threshold=3
    )
    assert blocked is True
    assert name == "consecutive tool calls"
    assert count == 3


def test_mixed_tool_round_counts_once_in_consecutive_streak() -> None:
    blocked, _, count = check_consecutive_tool_calls(
        [_tc("read_file", filename="one.py")], threshold=3
    )
    assert blocked is False
    assert count == 1

    blocked, name, count = check_consecutive_tool_calls(
        [
            _tc("read_file", filename="two.py"),
            _tc("list_dir", path="."),
        ],
        threshold=3,
    )
    assert blocked is False
    assert name == "consecutive tool calls"
    assert count == 2

    blocked, name, count = check_consecutive_tool_calls(
        [_tc("search_web", q="different")], threshold=3
    )
    assert blocked is True
    assert name == "consecutive tool calls"
    assert count == 3


def test_empty_round_resets_consecutive_tool_calls() -> None:
    check_consecutive_tool_calls([_tc("add_long_memory", note="one")], threshold=2)
    check_consecutive_tool_calls([])
    blocked, _, count = check_consecutive_tool_calls(
        [_tc("add_long_memory", note="two")], threshold=2
    )
    assert blocked is False
    assert count == 1


def test_general_tool_same_args_blocked_at_threshold() -> None:
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_current_location")])
        assert blocked is False

    blocked, name, count = check_general_tool_loop([_tc("get_current_location")])
    assert blocked is True
    assert name == "get_current_location"
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
        blocked, _, _ = check_general_tool_loop([_tc("get_current_location")])
        assert blocked is False
    blocked, name, count = check_general_tool_loop([_tc("get_current_location")])
    assert blocked is True
    assert name == "get_current_location"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD


def test_different_fingerprint_resets_other_counters() -> None:
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_current_location")])
        assert blocked is False
    assert any(
        k.startswith("tool:get_current_location:") for k in _TOOL_CALL_FINGERPRINTS
    )

    # Different fingerprint should drop the previous streak.
    blocked, _, _ = check_general_tool_loop(
        [_tc("get_weather_wttr", city="", lat=1.0, lon=2.0)]
    )
    assert blocked is False
    assert not any(
        k.startswith("tool:get_current_location:") for k in _TOOL_CALL_FINGERPRINTS
    )
    assert any(k.startswith("tool:get_weather_wttr:") for k in _TOOL_CALL_FINGERPRINTS)

    # Previous GPS streak must not carry over.
    for _ in range(_GENERAL_TOOL_LOOP_THRESHOLD - 1):
        blocked, _, _ = check_general_tool_loop([_tc("get_current_location")])
        assert blocked is False
    blocked, name, count = check_general_tool_loop([_tc("get_current_location")])
    assert blocked is True
    assert name == "get_current_location"
    assert count == _GENERAL_TOOL_LOOP_THRESHOLD


def test_tool_round_limit_clears_incomplete_responses_continuation() -> None:
    from types import SimpleNamespace

    from uagent.uagent_llm import _clear_responses_after_tool_loop

    reasons: list[str] = []
    state = {
        "previous_response_id": "resp_incomplete",
        "active_response_id": "resp_incomplete",
    }
    core = SimpleNamespace(
        responses_runtime=SimpleNamespace(
            clear_continuation=lambda reason: reasons.append(reason)
        ),
        responses_state=state,
        clear_responses_continuation=lambda: (
            state.pop("previous_response_id", None),
            state.pop("active_response_id", None),
        ),
    )

    _clear_responses_after_tool_loop(core, reason="tool_round_limit")

    assert reasons == ["tool_round_limit"]
    assert "previous_response_id" not in state
    assert "active_response_id" not in state


def test_loop_guard_clears_incomplete_responses_continuation() -> None:
    from types import SimpleNamespace

    from uagent.uagent_llm import _clear_responses_after_tool_loop

    calls: list[str] = []

    class Runtime:
        def clear_continuation(self, reason: str) -> None:
            calls.append(reason)

    state = {
        "previous_response_id": "resp_incomplete",
        "active_response_id": "resp_incomplete",
    }
    core = SimpleNamespace(
        responses_runtime=Runtime(),
        responses_state=state,
        clear_responses_continuation=lambda: (
            state.pop("previous_response_id", None),
            state.pop("active_response_id", None),
        ),
    )

    _clear_responses_after_tool_loop(core)

    assert calls == ["tool_loop_guard"]
    assert "previous_response_id" not in state
    assert "active_response_id" not in state
