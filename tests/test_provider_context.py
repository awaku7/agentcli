from __future__ import annotations

from uagent.runtime.provider_context import (
    apply_recovery_projection,
    project_messages_for_provider,
)


def test_recovery_projection_omits_explicit_indexes_without_mutation() -> None:
    source = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]

    projected = apply_recovery_projection(
        tuple(source), {"omitted_message_indexes": (1,)}
    )

    assert [message["content"] for message in projected] == ["one", "three"]
    assert source[1]["content"] == "two"


def test_recovery_projection_fails_open_for_malformed_indexes() -> None:
    source = [{"role": "user", "content": "one"}]

    projected = apply_recovery_projection(source, {"omitted_message_indexes": "bad"})

    assert projected == source


def test_provider_projection_isolated_and_normalizes_tool_content() -> None:
    source = [
        {
            "role": "tool",
            "content": {"ok": True},
            "_uagent_internal": "hidden",
            "attachments": [{"path": "result.png"}],
        }
    ]

    projected = project_messages_for_provider(source, provider="gemini")

    assert projected[0]["content"] == '{"ok": true}'
    assert "_uagent_internal" not in projected[0]
    assert projected[0]["attachments"] == [{"path": "result.png"}]
    assert source[0]["content"] == {"ok": True}


def test_deepseek_responses_search_state_is_retained_for_legacy_replay() -> None:
    source = [
        {
            "role": "assistant",
            "content": "",
            "_responses_output_items": [
                {
                    "type": "tool_search_call",
                    "call_id": "call_search_1",
                    "execution": "client",
                    "arguments": {"query": "weather"},
                }
            ],
        }
    ]

    projected = project_messages_for_provider(
        source,
        provider="deepseek",
        preserve_responses_output_items=True,
    )
    stripped = project_messages_for_provider(source, provider="deepseek")

    assert (
        projected[0]["_responses_output_items"] == source[0]["_responses_output_items"]
    )
    assert "_responses_output_items" not in stripped[0]
