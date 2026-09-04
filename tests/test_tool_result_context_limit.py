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
