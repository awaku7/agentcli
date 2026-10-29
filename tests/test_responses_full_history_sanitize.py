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


def test_full_history_drops_chat_reasoning_extension() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {
            "role": "assistant",
            "content": "回答",
            "reasoning_content": "内部推論",
        },
        {"role": "user", "content": "続けて"},
    ]

    _instructions, input_msgs, _tools = build_responses_request(
        messages,
        send_tools_this_round=False,
        provider="azure",
        previous_response_id=None,
    )

    assert all("reasoning_content" not in m for m in input_msgs)
    assert messages[1]["reasoning_content"] == "内部推論"


def test_vllm_stateless_full_history_keeps_tool_result() -> None:
    messages = [
        {"role": "user", "content": "今日の天気"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_weather",
                    "type": "function",
                    "function": {
                        "name": "get_weather_wttr",
                        "arguments": '{"city":"東京"}',
                    },
                }
            ],
            "_responses_output_items": [
                {
                    "type": "function_call",
                    "id": "fc_weather",
                    "call_id": "call_weather",
                    "name": "get_weather_wttr",
                    "arguments": '{"city":"東京"}',
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_weather",
            "name": "get_weather_wttr",
            "content": "東京: 晴れ、最高 31℃",
        },
        {"role": "user", "content": "気温も教えて"},
    ]

    instructions, input_msgs, _tools = build_responses_request(
        messages,
        send_tools_this_round=True,
        provider="vllm",
        previous_response_id=None,
    )

    serialized = str(input_msgs)
    assert "function_call_output" not in serialized
    assert "東京: 晴れ、最高 31℃" in serialized
    assert "Tool 'get_weather_wttr' returned result" in serialized
    assert "get_weather_wttr" in (instructions or "")
