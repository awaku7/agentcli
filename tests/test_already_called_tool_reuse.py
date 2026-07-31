from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.llm_flow_helpers import _execute_tool_calls
from uagent import tools


class _Core:
    show_tool_output = False

    def set_status(self, busy, label):
        return None

    def log_message(self, msg):
        return None


def _tc(call_id: str, name: str, **args) -> dict:
    return {
        "id": call_id,
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def test_identical_tool_call_returns_already_called(monkeypatch) -> None:
    calls = []

    def _fake_run(name, args):
        calls.append((name, args))
        return json.dumps({"ok": True, "n": len(calls)}, ensure_ascii=False)

    monkeypatch.setattr(tools, "run_tool", _fake_run)
    monkeypatch.setattr(tools, "is_parallel_safe", lambda _name: False)

    messages: list[dict] = []
    cache: dict[str, str] = {}
    core = _Core()

    executed1, fresh1 = _execute_tool_calls(
        tool_calls_list=[_tc("c1", "get_windows_gps")],
        messages=messages,
        core=core,
        cache_mgr=SimpleNamespace(record_file_access=lambda _p: None),
        tool_result_cache=cache,
        use_tool_result_cache=False,
    )
    executed2, fresh2 = _execute_tool_calls(
        tool_calls_list=[_tc("c2", "get_windows_gps")],
        messages=messages,
        core=core,
        cache_mgr=SimpleNamespace(record_file_access=lambda _p: None),
        tool_result_cache=cache,
        use_tool_result_cache=False,
    )

    assert len(calls) == 1
    assert executed1 is True and len(fresh1) == 1
    assert executed2 is False and fresh2 == []
    assert messages[0]["role"] == "tool"
    assert messages[1]["role"] == "tool"
    assert (
        "Already called this tool with the same arguments earlier"
        in messages[1]["content"]
    )
    assert "Do NOT call this tool again" in messages[1]["content"]
    assert '"n": 1' in messages[1]["content"]
    # Must NOT inject a synthetic user note (breaks Responses tool continuation).
    assert not any(
        m.get("role") == "user" and "SYSTEM NOTE" in str(m.get("content") or "")
        for m in messages
    )


def test_repeatable_tools_are_not_short_circuited(monkeypatch) -> None:
    calls = []

    def _fake_run(name, args):
        calls.append((name, dict(args)))
        return json.dumps({"ok": True, "n": len(calls)}, ensure_ascii=False)

    monkeypatch.setattr(tools, "run_tool", _fake_run)
    monkeypatch.setattr(tools, "is_parallel_safe", lambda _name: False)

    messages: list[dict] = []
    cache: dict[str, str] = {}
    core = _Core()

    for i in range(2):
        _execute_tool_calls(
            tool_calls_list=[_tc(f"c{i}", "python_exec", code="print(1)")],
            messages=messages,
            core=core,
            cache_mgr=SimpleNamespace(record_file_access=lambda _p: None),
            tool_result_cache=cache,
            use_tool_result_cache=False,
        )

    assert len(calls) == 2
    assert "Already called" not in messages[1]["content"]
