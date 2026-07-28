from __future__ import annotations

import json
from types import SimpleNamespace

from uagent import tools
from uagent.llm_flow_helpers import _execute_tool_calls
from uagent.uagent_llm import (
    _GENERAL_TOOL_LOOP_THRESHOLD,
    _TOOL_CALL_FINGERPRINTS,
    check_general_tool_loop,
)


def setup_function() -> None:
    _TOOL_CALL_FINGERPRINTS.clear()


def _tc(call_id: str, name: str, **args) -> dict:
    return {
        "id": call_id,
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


class _Core:
    show_tool_output = False

    def set_status(self, busy, label):
        return None

    def log_message(self, msg):
        return None


def test_cache_reuse_does_not_count_toward_general_loop(monkeypatch) -> None:
    n = {"c": 0}

    def _fake_run(name, args):
        n["c"] += 1
        return json.dumps({"ok": True, "n": n["c"]}, ensure_ascii=False)

    monkeypatch.setattr(tools, "run_tool", _fake_run)
    monkeypatch.setattr(tools, "is_parallel_safe", lambda _name: False)

    messages: list[dict] = []
    cache: dict[str, str] = {}
    core = _Core()

    # One fresh execution + many identical reuses should not trip the detector.
    for i in range(_GENERAL_TOOL_LOOP_THRESHOLD + 3):
        executed, fresh = _execute_tool_calls(
            tool_calls_list=[
                _tc(f"c{i}", "get_weather_wttr", city="", lat=34.654, lon=135.7845)
            ],
            messages=messages,
            core=core,
            cache_mgr=SimpleNamespace(record_file_access=lambda _p: None),
            tool_result_cache=cache,
            use_tool_result_cache=False,
        )
        blocked, name, _count = check_general_tool_loop(fresh)
        assert blocked is False
        if i == 0:
            assert executed is True
            assert len(fresh) == 1
            assert fresh[0]["function"]["name"] == "get_weather_wttr"
        else:
            assert executed is False
            assert fresh == []

    # Only the first real execution was counted.
    assert (
        _TOOL_CALL_FINGERPRINTS.get(
            'tool:get_weather_wttr:{"city": "", "lat": 34.654, "lon": 135.7845}'
        )
        == 1
    )
    assert n["c"] == 1
