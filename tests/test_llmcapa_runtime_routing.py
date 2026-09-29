from __future__ import annotations

from types import SimpleNamespace

from uagent.llm_round_helpers import _resolve_round_runtime_flags
from uagent.runtime.capability_resolver import CapabilityResolver, CapabilityState


def _core() -> SimpleNamespace:
    return SimpleNamespace(set_status=lambda *args: None)


def test_explicit_responses_request_respects_model_false_capability(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "responses_api" else None
    )

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="foundry_local",
        depname="phi-4-mini",
        capability_resolver=resolver,
    ) == (False, False)


def test_explicit_responses_request_allows_positive_model_capability(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_STREAMING", "0")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: True if feature == "responses_api" else None
    )

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="openai",
        depname="example-model",
        capability_resolver=resolver,
    ) == (True, False)


def test_streaming_false_model_capability_disables_streaming_for_any_provider(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_RESPONSES", "0")
    monkeypatch.setenv("UAGENT_STREAMING", "1")

    def lookup(feature: str, *_args):
        if feature == "streaming":
            return False
        return None

    resolver = CapabilityResolver(feature_lookup=lookup)

    assert _resolve_round_runtime_flags(
        tr_cfg=None,
        core=_core(),
        provider="foundry_local",
        depname="phi-4-mini",
        capability_resolver=resolver,
    ) == (False, False)


def test_tool_discovery_respects_explicit_responses_false_capability(monkeypatch) -> None:
    from uagent.runtime.tool_discovery import (
        ToolDiscoveryMode,
        resolve_tool_discovery_from_environment,
    )

    monkeypatch.setenv("UAGENT_PROVIDER", "foundry_local")
    monkeypatch.setenv("UAGENT_FOUNDRY_LOCAL_DEPNAME", "phi-4-mini")
    monkeypatch.setenv("UAGENT_RESPONSES", "1")
    monkeypatch.setenv("UAGENT_GPT54_TOOL_SEARCH", "native")
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: False if feature == "responses_api" else None
    )

    decision = resolve_tool_discovery_from_environment(
        capability_resolver=resolver,
    )

    assert decision.mode is ToolDiscoveryMode.SELECTED_SCHEMAS
    assert decision.reason == "responses_api_disabled"


def test_tool_search_is_authorized_by_capabilities_not_provider_name() -> None:
    from uagent.runtime.tool_discovery import ToolDiscoveryMode, resolve_tool_discovery

    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: (
            True if feature in {"responses_api", "tool_search"} else None
        )
    )

    decision = resolve_tool_discovery(
        provider="openrouter",
        depname="future-tool-search-model",
        use_responses_api=True,
        configured_mode="native",
        capability_resolver=resolver,
    )

    assert decision.mode is ToolDiscoveryMode.NATIVE_SEARCH


def test_core_model_capabilities_are_narrowed_by_llmcapa() -> None:
    model_values = {
        "streaming": False,
        "function_calling": False,
        "vision": False,
    }
    resolver = CapabilityResolver(
        feature_lookup=lambda feature, *_: model_values.get(feature)
    )

    snapshot = resolver.resolve("openai", "example-model")

    assert snapshot.streaming.state is CapabilityState.FALSE
    assert snapshot.tools.state is CapabilityState.FALSE
    assert snapshot.vision.state is CapabilityState.FALSE


def test_provider_implementation_remains_outer_capability_gate() -> None:
    resolver = CapabilityResolver(feature_lookup=lambda *_: True)

    snapshot = resolver.resolve("unknown-provider", "example-model")

    assert snapshot.streaming.state is CapabilityState.FALSE
    assert snapshot.tools.state is CapabilityState.FALSE
    assert snapshot.vision.state is CapabilityState.FALSE
