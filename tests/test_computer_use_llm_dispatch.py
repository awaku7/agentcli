import json
from types import SimpleNamespace

from uagent.llm_flow_helpers import _execute_tool_calls


class Cache:
    def record_file_access(self, filename):
        pass


def test_computer_tool_calls_use_core_handler(monkeypatch):
    calls = []
    core = SimpleNamespace(
        computer_use_handler=lambda **kwargs: calls.append(kwargs)
        or json.dumps({"ok": True}),
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda *args: None,
    )
    messages = []
    tool_calls = [
        {
            "id": "computer-1",
            "type": "function",
            "function": {
                "name": "computer",
                "arguments": json.dumps({"action": "screenshot"}),
            },
        }
    ]

    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *a: False
    )
    executed, fresh = _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=Cache(),
    )

    assert executed is True
    assert fresh == tool_calls
    assert calls[0]["action"]["action"] == "screenshot"
    assert messages[-1]["content"] == json.dumps({"ok": True})
