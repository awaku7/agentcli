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
    assert provider_candidates("foundry_local") == ["foundry_local", "foundry-local"]


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


def test_foundry_local_responses_unknown_fails_closed(monkeypatch) -> None:
    import uagent.llmcapa_util as util

    monkeypatch.setattr(
        util,
        "supports_feature",
        lambda feature, model, provider, default=None: None,
    )

    assert (
        util.supports_responses_api("phi-4-mini", "foundry_local", default=True)
        is False
    )


def test_explicit_responses_setting_cannot_override_foundry_unknown(monkeypatch) -> None:
    import uagent.llmcapa_util as util

    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setattr(
        util,
        "supports_feature",
        lambda feature, model, provider, default=None: None,
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


def test_foundry_local_startup_banner_shows_normalized_base_url(monkeypatch) -> None:
    from uagent.runtime.runtime_banner import build_startup_banner

    monkeypatch.setenv("UAGENT_PROVIDER", "foundry_local")
    monkeypatch.setenv("UAGENT_FOUNDRY_LOCAL_BASE_URL", "http://localhost:5272/v1/")
    core = SimpleNamespace(normalize_url=lambda value: value.rstrip("/"))
    banner = build_startup_banner(core=core, workdir=".", workdir_source="test")
    assert "base_url = http://localhost:5272/v1" in banner
    assert "base_url = http://localhost:5272/v1/" not in banner


def test_foundry_local_feature_lookup_is_provider_scoped(monkeypatch) -> None:
    import uagent.llmcapa_util as util

    seen: dict[str, object] = {}

    def fake_get_capability(model, provider, *, scoped_only=False):
        seen["model"] = model
        seen["provider"] = provider
        seen["scoped_only"] = scoped_only
        return None

    monkeypatch.setattr(util, "get_capability", fake_get_capability)
    assert (
        util.supports_feature(
            "function_calling", "shared-model-name", "foundry_local", default=None
        )
        is None
    )
    assert seen == {
        "model": "shared-model-name",
        "provider": "foundry_local",
        "scoped_only": True,
    }


def test_foundry_local_strict_candidate_uses_catalog_provider_name() -> None:
    import uagent.llmcapa_util as util

    assert util._STRICT_PROVIDER_CANDIDATES["foundry_local"] == ("foundry-local",)
