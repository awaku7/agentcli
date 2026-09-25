from __future__ import annotations

from uagent.runtime.observability.privacy import sanitize_attributes
from uagent.runtime.observability.semantic_mapping import map_span


def test_privacy_filter_excludes_identity_secrets_and_content_by_default() -> None:
    safe = sanitize_attributes(
        {
            "uag.tool.name": "read_file",
            "authorization": "Bearer secret",
            "session_id": "session-1",
            "principal_id": "user-A",
            "gen_ai.input.messages.content": "private prompt",
            "uag.status": "ok",
        }
    )

    assert safe == {"uag.tool.name": "read_file", "uag.status": "ok"}


def test_capture_content_never_allows_identity_or_secret_fields() -> None:
    safe = sanitize_attributes(
        {
            "uag.content": "operator-enabled content",
            "access_token": "secret",
            "room_id": "shared",
        },
        capture_content=True,
    )

    assert safe == {"uag.content": "operator-enabled content"}


def test_semantic_mapping_isolated_from_runtime_operation_names() -> None:
    mapped = map_span(
        "chat",
        {
            "uag.llm.provider": "openai",
            "uag.llm.model": "gpt-test",
        },
    )

    assert mapped.name == "chat gpt-test"
    assert mapped.attributes["gen_ai.operation.name"] == "chat"
    assert mapped.attributes["gen_ai.request.model"] == "gpt-test"
    assert mapped.attributes["gen_ai.provider.name"] == "openai"
