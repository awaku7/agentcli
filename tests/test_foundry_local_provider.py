"""Focused tests for the Microsoft Foundry Local UAG provider."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from uagent.providers import llm_foundry_local


def test_normalize_foundry_local_base_url_is_loopback_only() -> None:
    assert (
        llm_foundry_local.normalize_foundry_local_base_url("http://localhost:5272")
        == "http://localhost:5272/v1"
    )
    assert (
        llm_foundry_local.normalize_foundry_local_base_url("http://127.0.0.1:5272/v1")
        == "http://127.0.0.1:5272/v1"
    )
    with pytest.raises(ValueError, match="loopback"):
        llm_foundry_local.normalize_foundry_local_base_url(
            "https://example.com:5272/v1"
        )
    with pytest.raises(ValueError, match="path"):
        llm_foundry_local.normalize_foundry_local_base_url(
            "http://localhost:5272/not-foundry"
        )


def test_make_client_requires_explicit_local_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_FOUNDRY_LOCAL_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="UAGENT_FOUNDRY_LOCAL_BASE_URL"):
        llm_foundry_local.make_foundry_local_client(object(), "phi-4-mini")


def test_make_client_uses_openai_compatible_endpoint(monkeypatch) -> None:
    created: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("UAGENT_FOUNDRY_LOCAL_BASE_URL", "http://localhost:5272")
    monkeypatch.delenv("UAGENT_FOUNDRY_LOCAL_API_KEY", raising=False)
    monkeypatch.setattr(
        "uagent.providers.util_providers.make_httpx_client",
        lambda: "httpx-client",
    )

    client, model = llm_foundry_local.make_foundry_local_client(object(), "phi-4-mini")

    assert isinstance(client._inner, FakeOpenAI)
    assert model == "phi-4-mini"
    assert created["base_url"] == "http://localhost:5272/v1"
    assert created["api_key"] == "dummy"
    assert created["http_client"] == "httpx-client"


def test_client_boundary_drops_tools_without_positive_llmcapa_evidence(
    monkeypatch,
) -> None:
    sent: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            sent.update(kwargs)
            return "ok"

    inner = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    client = llm_foundry_local._FoundryLocalClientProxy(inner)
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_feature",
        lambda feature, model, provider, default=None: None,
    )

    result = client.chat.completions.create(
        model="phi-4-mini",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function"}],
        tool_choice="auto",
    )

    assert result == "ok"
    assert "tools" not in sent
    assert "tool_choice" not in sent


def test_client_boundary_preserves_tools_with_positive_llmcapa_evidence(
    monkeypatch,
) -> None:
    sent: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            sent.update(kwargs)
            return "ok"

    inner = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    client = llm_foundry_local._FoundryLocalClientProxy(inner)
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_feature",
        lambda feature, model, provider, default=None: True,
    )

    tools = [{"type": "function"}]
    result = client.chat.completions.create(
        model="future-tool-model",
        messages=[{"role": "user", "content": "hello"}],
        tools=tools,
        tool_choice="auto",
    )

    assert result == "ok"
    assert sent["tools"] == tools
    assert sent["tool_choice"] == "auto"
