from __future__ import annotations

from uagent.core import sanitize_messages_for_tools


def test_sanitize_drops_orphan_tool_after_interrupted_block() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "tool_a", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "ok"},
        {"role": "assistant", "content": "final"},
        {"role": "tool", "tool_call_id": "call_1", "content": "orphan"},
    ]

    cleaned = sanitize_messages_for_tools(messages)

    assert cleaned == messages[:4]


def test_sanitize_keeps_contiguous_tool_block() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "tool_a", "arguments": "{}"},
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "tool_b", "arguments": "{}"},
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "ok1"},
        {"role": "tool", "tool_call_id": "call_2", "content": "ok2"},
        {"role": "assistant", "content": "final"},
    ]

    cleaned = sanitize_messages_for_tools(messages)

    assert cleaned == messages
