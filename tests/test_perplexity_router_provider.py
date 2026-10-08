from __future__ import annotations

from typing import Any

import pytest

from uagent.providers import util_providers
from uagent.providers.openai_projection_policy import build_openai_projection
from uagent.llmcapa_util import provider_allows_responses_api
from uagent.providers.provider_caps import (
    DEFAULT_PROVIDER_REGISTRY,
    RESPONSES_PROVIDERS,
)


class _Core:
    credential_store = None

    def get_env(self, name: str, default: str | None = None) -> str | None:
        import os

        return os.environ.get(name, default)

    def get_env_url(self, name: str, default: str | None = None) -> str:
        return (self.get_env(name, default) or "").strip()


def test_perplexity_client_uses_router_base_url_and_model(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url, http_client=None):
            captured.update(
                api_key=api_key,
                base_url=base_url,
                http_client=http_client,
            )

    monkeypatch.setenv("UAGENT_PROVIDER", "perplexity")
    monkeypatch.setenv("UAGENT_PERPLEXITY_API_KEY", "test-router-key")
    monkeypatch.delenv("UAGENT_PERPLEXITY_BASE_URL", raising=False)
    monkeypatch.setenv("UAGENT_PERPLEXITY_DEPNAME", "perplexity/kimi-k3")
    monkeypatch.setattr(util_providers, "_ensure_provider_dependency", lambda _: None)
    monkeypatch.setattr(util_providers, "make_httpx_client", lambda **_: None)
    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    provider, client, model = util_providers.make_client(_Core())

    assert provider == "perplexity"
    assert isinstance(client, FakeOpenAI)
    assert model == "perplexity/kimi-k3"
    assert captured["api_key"] == "test-router-key"
    assert captured["base_url"] == "https://api.perplexity.ai/router/v1"


def test_perplexity_responses_projection_omits_unsupported_context_management(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "UAGENT_REASONING",
        "UAGENT_VERBOSITY",
        "UAGENT_MAX_TOKENS",
        "UAGENT_TOP_P",
    ):
        monkeypatch.delenv(name, raising=False)

    projection = build_openai_projection(
        provider="perplexity",
        model="perplexity/kimi-k3",
        transport="responses",
        messages=[{"role": "user", "content": "hello"}],
        send_tools=False,
        compaction_threshold=1000,
    )

    assert (
        "responses"
        in DEFAULT_PROVIDER_REGISTRY.resolve(
            "perplexity", "perplexity/kimi-k3"
        ).capabilities
    )
    assert "perplexity" in RESPONSES_PROVIDERS
    assert provider_allows_responses_api("perplexity", "perplexity/kimi-k3")
    assert "context_management" not in projection.options


def test_perplexity_responses_maps_json_object_to_strict_json_schema(monkeypatch):
    monkeypatch.setattr(
        "uagent.providers.openai_projection_policy.native_structured_output_request_for_runtime",
        lambda *args, **kwargs: {"type": "json_object"},
    )
    projection = build_openai_projection(
        provider="perplexity",
        model="perplexity/kimi-k3",
        transport="responses",
        messages=[{"role": "user", "content": "return json"}],
        send_tools=False,
        compaction_threshold=1000,
    )

    assert projection.options["text"]["format"] == {
        "type": "json_schema",
        "name": "json_output",
        "strict": True,
        "schema": {"type": "object"},
    }


def test_perplexity_responses_are_stateless() -> None:
    from uagent.providers.responses_manager import get_responses_capabilities

    capabilities = get_responses_capabilities("perplexity")
    assert capabilities.create is True
    assert capabilities.streaming is True
    assert capabilities.previous_response_id is False
    assert capabilities.retrieve is False
    assert capabilities.compact is False
