from __future__ import annotations

from uagent.runtime.provider_context import project_messages_for_provider


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
