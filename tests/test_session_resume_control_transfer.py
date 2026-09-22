from __future__ import annotations

import json
from types import SimpleNamespace

from uagent.llm_flow_helpers import _execute_tool_calls


class _Cache:
    def record_file_access(self, filename):
        pass


def test_session_resume_is_exclusive_and_requests_round_stop(monkeypatch):
    calls = []

    def run_tool(name, args):
        calls.append(name)
        if name == "session_resume":
            return json.dumps(
                {
                    "ok": True,
                    "status": "queued",
                    "control_transfer": True,
                    "session_id": "yesterday-session",
                }
            )
        raise AssertionError(f"unexpected stale-session tool execution: {name}")

    monkeypatch.setattr(
        "uagent.llm_flow_helpers.tools.is_parallel_safe", lambda *args: False
    )
    monkeypatch.setattr("uagent.llm_flow_helpers.tools.run_tool", run_tool)

    messages = []
    core = SimpleNamespace(
        show_tool_output=False,
        set_status=lambda *args: None,
        log_message=lambda message: None,
    )
    tool_calls = [
        {
            "id": "resume-1",
            "type": "function",
            "function": {"name": "session_resume", "arguments": "{}"},
        },
        {
            "id": "list-1",
            "type": "function",
            "function": {"name": "list_dir", "arguments": "{}"},
        },
    ]

    executed, fresh = _execute_tool_calls(
        tool_calls_list=tool_calls,
        messages=messages,
        core=core,
        cache_mgr=_Cache(),
    )

    assert executed is True
    assert calls == ["session_resume"]
    assert [item["id"] for item in fresh] == ["resume-1"]
    assert core._session_resume_control_transfer is True
    assert len(messages) == 1
    assert messages[0]["name"] == "session_resume"
