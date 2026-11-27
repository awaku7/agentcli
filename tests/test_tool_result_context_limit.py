from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.llm_flow_helpers import _execute_tool_calls


class _Cache:
    def record_file_access(self, filename):
        pass


def test_tool_result_is_limited_before_message_history(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_CHARS", "100")
    monkeypatch.delenv("UAGENT_HISTORY_TOOL_RESULT_MAX_CHARS", raising=False)
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *args: False
    )
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool", lambda name, args: "x" * 300
    )

    messages: list[dict] = []
    core = SimpleNamespace(
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda message: None,
    )
    tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "calculator", "arguments": json.dumps({})},
        }
    ]

    executed, fresh = _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=_Cache(),
    )

    assert executed is True
    assert fresh == tool_calls
    assert len(messages) == 1
    assert len(messages[0]["content"]) == 100
    assert "original length=300" in messages[0]["content"]


def test_provider_disallowed_management_calls_are_not_executed(
    monkeypatch, capsys
) -> None:
    from uagent.runtime.tool_discovery import MANAGEMENT_TOOL_NAMES

    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *args: False
    )
    executed: list[str] = []
    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.run_tool",
        lambda name, _args: executed.append(name) or "should not run",
    )
    messages: list[dict] = []
    core = SimpleNamespace(
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda _message: None,
    )
    calls = [
        {
            "id": f"call-{name}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps({})},
        }
        for name in sorted(MANAGEMENT_TOOL_NAMES)
    ]

    executed_new_tool, fresh_calls = _execute_tool_calls(
        tool_calls_list=calls,
        messages=messages,
        core=core,
        cache_mgr=_Cache(),
        disallowed_tool_names=MANAGEMENT_TOOL_NAMES,
    )

    assert executed == []
    assert executed_new_tool is False
    assert fresh_calls == []
    assert {message["name"] for message in messages} == MANAGEMENT_TOOL_NAMES
    assert all("unavailable on this provider route" in m["content"] for m in messages)
    warning_output = capsys.readouterr().out
    assert "blocked unadvertised management tool call" in warning_output
    assert all(name in warning_output for name in MANAGEMENT_TOOL_NAMES)
