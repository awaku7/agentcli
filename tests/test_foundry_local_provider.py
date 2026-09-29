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


def test_make_client_uses_plain_openai_compatible_client(monkeypatch) -> None:
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

    assert isinstance(client, FakeOpenAI)
    assert model == "phi-4-mini"
    assert created["base_url"] == "http://localhost:5272/v1"
    assert created["api_key"] == "dummy"
    assert created["http_client"] == "httpx-client"


def test_make_client_resolves_api_key_from_credential_store(monkeypatch) -> None:
    created: dict[str, object] = {}
    seen: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            created.update(kwargs)

    def fake_get_provider_api_key(provider, *, store=None, env_getter=None):
        seen["provider"] = provider
        seen["store"] = store
        seen["env_getter"] = env_getter
        return "stored-secret"

    env_values = {"UAGENT_FOUNDRY_LOCAL_BASE_URL": "http://localhost:5272"}
    core = SimpleNamespace(
        credential_store="credential-store",
        get_env=lambda name: env_values.get(name),
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setattr(
        llm_foundry_local,
        "get_provider_api_key",
        fake_get_provider_api_key,
    )
    monkeypatch.setattr(
        "uagent.providers.util_providers.make_httpx_client",
        lambda: "httpx-client",
    )

    client, model = llm_foundry_local.make_foundry_local_client(core, "phi-4-mini")

    assert isinstance(client, FakeOpenAI)
    assert model == "phi-4-mini"
    assert seen["provider"] == "foundry_local"
    assert seen["store"] == "credential-store"
    assert seen["env_getter"] is core.get_env
    assert created["api_key"] == "stored-secret"
