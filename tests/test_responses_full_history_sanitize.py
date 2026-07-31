from __future__ import annotations

from uagent.providers.llm_openai_responses import build_responses_request


def test_full_history_skips_bare_function_call_items() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "news"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "arguments": "{}",
                    },
                }
            ],
            "_responses_output_items": [
                {"type": "reasoning", "id": "rs_1", "summary": []},
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "get_current_time",
                    "arguments": "{}",
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "name": "get_current_time",
            "content": "2026-07-19",
        },
        {"role": "user", "content": "おい"},
    ]

    _instructions, input_msgs, _tools = build_responses_request(
        messages,
        send_tools_this_round=False,
        provider="openai",
        previous_response_id=None,
    )

    types = [m.get("type") for m in input_msgs if isinstance(m, dict) and "type" in m]
    assert "function_call" not in types
    assert "function_call_output" not in types
    # tool result is converted to a user-role summary message
    assert any(
        m.get("role") == "user" and "get_current_time" in str(m.get("content"))
        for m in input_msgs
        if isinstance(m, dict)
    )
