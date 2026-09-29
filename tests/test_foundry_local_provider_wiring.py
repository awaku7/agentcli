"""Minimal provider and llmcapa wiring tests for Foundry Local."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from uagent.providers.provider_caps import ALL_PROVIDERS, DEFAULT_PROVIDER_REGISTRY
from uagent.providers.runtime_registry import supports_provider_runtime


def test_foundry_local_is_registered_as_local_chat_provider() -> None:
    assert "foundry_local" in ALL_PROVIDERS
    spec = DEFAULT_PROVIDER_REGISTRY.resolve("foundry_local")
    assert spec.name == "foundry_local"
    assert spec.auth_requirement == "local_endpoint"
    assert spec.supports_streaming is True
    assert "chat" in spec.capabilities
    assert "responses" in spec.capabilities
    assert supports_provider_runtime("foundry_local") is True


def test_foundry_local_uses_exact_llmcapa_provider_and_model(monkeypatch) -> None:
    import uagent.llmcapa_util as util

    calls: list[tuple[str, str | None]] = []
    capability = SimpleNamespace(
        provider="foundry-local",
        model_id="phi-4-mini",
        context_window=16384,
        max_output_tokens=4096,
    )

    def fake_get(model, provider=None):
        calls.append((model, provider))
        if model == "phi-4-mini" and provider == "foundry-local":
            return capability
        return None

    monkeypatch.setitem(sys.modules, "llmcapa", SimpleNamespace(get=fake_get))
    util.clear_capability_cache()
    try:
        resolved = util.get_capability("phi-4-mini", "foundry_local")
    finally:
        util.clear_capability_cache()

    assert resolved is capability
    assert calls == [("phi-4-mini", "foundry-local")]


def test_foundry_local_does_not_fall_back_to_another_provider(monkeypatch) -> None:
    import uagent.llmcapa_util as util

    calls: list[tuple[str, str | None]] = []
    cloud_capability = SimpleNamespace(
        provider="microsoft",
        model_id="shared-model-name",
        context_window=131072,
        max_output_tokens=8192,
    )

    def fake_get(model, provider=None):
        calls.append((model, provider))
        if provider is None:
            return cloud_capability
        return None

    monkeypatch.setitem(sys.modules, "llmcapa", SimpleNamespace(get=fake_get))
    util.clear_capability_cache()
    try:
        assert util.get_capability("shared-model-name", "foundry_local") is None
        assert util.get_context_window_details(
            "shared-model-name", "foundry_local"
        ) == (None, "unavailable")
        assert util.get_max_output_tokens("shared-model-name", "foundry_local") is None
    finally:
        util.clear_capability_cache()

    assert calls
    assert all(provider == "foundry-local" for _, provider in calls)


def test_foundry_local_default_model_is_phi_4_mini(monkeypatch) -> None:
    from uagent.providers.util_providers import get_model_name

    monkeypatch.setenv("UAGENT_PROVIDER", "foundry_local")
    monkeypatch.delenv("UAGENT_FOUNDRY_LOCAL_DEPNAME", raising=False)
    assert get_model_name() == "phi-4-mini"
