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
