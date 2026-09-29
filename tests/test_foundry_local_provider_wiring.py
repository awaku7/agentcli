"""Provider-registry and llmcapa routing tests for Foundry Local."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.llmcapa_util import provider_candidates
from uagent.providers.provider_caps import ALL_PROVIDERS, DEFAULT_PROVIDER_REGISTRY
from uagent.providers.runtime_registry import supports_provider_runtime
from uagent.providers.responses_manager import get_responses_capabilities
from uagent.runtime.capability_resolver import CapabilityResolver, CapabilityState
from uagent.llm_round_helpers import _resolve_round_runtime_flags


def test_foundry_local_is_registered_as_local_openai_compatible_provider() -> None:
    assert "foundry_local" in ALL_PROVIDERS
    spec = DEFAULT_PROVIDER_REGISTRY.resolve("foundry_local")
    assert spec.name == "foundry_local"
    assert spec.auth_requirement == "local_endpoint"
    assert spec.supports_streaming is True
    assert "responses" in spec.capabilities
    assert supports_provider_runtime("foundry_local") is True
    assert get_responses_capabilities("foundry_local").create is True


def test_foundry_local_maps_to_static_llmcapa_provider_name() -> None:
    candidates = provider_candidates("foundry_local")
    assert candidates[0] == "foundry_local"
    assert "foundry-local" in candidates


def test_foundry_local_tool_support_requires_positive_model_evidence() -> None:
    def lookup(feature: str, model: str, provider: str):
        assert model == "phi-4-mini"
        assert provider == "foundry_local"
        if feature == "function_calling":
            return True
        if feature == "responses_api":
            return False
        return None

    resolved = CapabilityResolver(feature_lookup=lookup).resolve(
        "foundry_local", "phi-4-mini"
    )
    assert resolved.tools.state is CapabilityState.TRUE_DOCUMENTED
    assert resolved.tools.is_native_allowed() is True
    assert resolved.responses_create.state is CapabilityState.FALSE
    assert resolved.responses_create.is_native_allowed() is False


def test_explicit_responses_setting_cannot_override_llmcapa_false(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_responses_api",
        lambda model, provider, default=None: False,
    )
    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="foundry_local",
        depname="phi-4-mini",
    )
    assert use_responses is False


def test_explicit_responses_setting_follows_llmcapa_true(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        "uagent.llmcapa_util.supports_responses_api",
        lambda model, provider, default=None: True,
    )
    use_responses, _streaming = _resolve_round_runtime_flags(
        tr_cfg=None,
        core=SimpleNamespace(),
        provider="foundry_local",
        depname="future-responses-model",
    )
    assert use_responses is True
