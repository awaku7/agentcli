from __future__ import annotations

from uagent.providers.responses_web_search_openai import (
    openai_web_search_tool_for_provider,
)


def test_hosted_web_search_is_limited_to_openai_compatible_providers(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_OPENAI_WEB_SEARCH", "1")

    assert openai_web_search_tool_for_provider("openai") == {"type": "web_search"}
    assert openai_web_search_tool_for_provider("azure") == {"type": "web_search"}
    assert openai_web_search_tool_for_provider("meta") is None
    assert openai_web_search_tool_for_provider("openrouter") is None
