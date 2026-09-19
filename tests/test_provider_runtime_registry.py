from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.providers.inception_runtime import InceptionProviderRuntime
from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime
from uagent.providers.pfn_runtime import PfnProviderRuntime
from uagent.providers.runtime_registry import (
    build_provider_runtime_registry,
    supports_provider_runtime,
)
from uagent.runtime.capability_resolver import (
    CapabilityResolver,
    ProviderCapabilitySnapshot,
)
from uagent.runtime.round_contracts import RoundIdentifiers, RoundTransportSelection


class _RecordingCapabilityResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self._fallback = CapabilityResolver()

    def resolve(
        self, provider: str, model: str = "", transport: str = "chat_completions"
    ) -> ProviderCapabilitySnapshot:
        self.calls.append((provider, model, transport))
        return self._fallback.resolve(provider, model, transport)


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1)


def test_registry_builds_openai_and_azure_compatible_adapters() -> None:
    for provider in (
        "openai",
        "azure",
        "nvidia",
        "openrouter",
        "moonshot",
        "alibaba",
        "sakana",
        "bedrock",
        "ollama",
        "lmstudio",
        "meta",
    ):
        registry = build_provider_runtime_registry(
            provider=provider,
            client=SimpleNamespace(),
            model="gpt-test",
            identifiers=_identifiers(),
        )
        runtime = registry.resolve(provider)
        assert isinstance(runtime, OpenAICompatibleRuntime)
        assert runtime.capabilities.provider == provider
        assert runtime.capabilities.transport == "chat_completions"
        assert registry.capability_snapshot(provider) is runtime.capabilities
        assert registry.providers() == (provider,)


def test_registry_builds_pfn_specialized_adapter() -> None:
    registry = build_provider_runtime_registry(
        provider="pfn",
        client=SimpleNamespace(),
        model="plamo-test",
        identifiers=_identifiers(),
    )

    runtime = registry.resolve("pfn")
    assert isinstance(runtime, PfnProviderRuntime)
    assert runtime.capabilities.provider == "pfn"
    assert supports_provider_runtime("pfn") is True


def test_registry_adapters_use_injected_capability_resolver() -> None:
    resolver = _RecordingCapabilityResolver()

    build_provider_runtime_registry(
        provider="openai",
        client=SimpleNamespace(),
        model="gpt-test",
        identifiers=_identifiers(),
        transport="responses",
        capability_resolver=resolver,
    )
    build_provider_runtime_registry(
        provider="inception",
        client=SimpleNamespace(),
        model="mercury-test",
        identifiers=_identifiers(),
        capability_resolver=resolver,
    )

    assert resolver.calls == [
        ("openai", "gpt-test", "responses"),
        ("inception", "mercury-test", "chat_completions"),
    ]


def test_registry_uses_resolved_transport_selection_over_legacy_flags() -> None:
    selection = RoundTransportSelection.from_flags(
        use_responses_api=True,
        stream_responses=False,
    )

    registry = build_provider_runtime_registry(
        provider="openai",
        client=SimpleNamespace(),
        model="gpt-test",
        identifiers=_identifiers(),
        transport="chat_completions",
        streaming=True,
        transport_selection=selection,
    )

    runtime = registry.resolve("openai")
    assert isinstance(runtime, OpenAICompatibleRuntime)
    assert runtime._transport == "responses"
    assert runtime._streaming is False


def test_registry_keeps_inception_adapter_registration() -> None:
    registry = build_provider_runtime_registry(
        provider="inception",
        client=SimpleNamespace(),
        model="mercury-test",
        identifiers=_identifiers(),
    )

    runtime = registry.resolve("inception")
    assert isinstance(runtime, InceptionProviderRuntime)
    assert runtime.capabilities.provider == "inception"


def test_registry_rejects_unmigrated_provider_instead_of_guessing() -> None:
    with pytest.raises(ValueError, match="not migrated"):
        build_provider_runtime_registry(
            provider="gemini",
            client=SimpleNamespace(),
            model="gemini-test",
            identifiers=_identifiers(),
        )


def test_registry_support_check_is_normalized_and_has_one_source_of_truth(
    monkeypatch,
) -> None:
    assert supports_provider_runtime(" OPENAI ") is True
    assert supports_provider_runtime("Azure") is True
    assert supports_provider_runtime("inception") is True
    assert supports_provider_runtime("nvidia") is True
    assert supports_provider_runtime("gemini") is False
    assert supports_provider_runtime("openrouter") is True
    assert supports_provider_runtime("moonshot") is True
    assert supports_provider_runtime("alibaba") is True
    assert supports_provider_runtime("sakana") is True
    assert supports_provider_runtime("bedrock") is True
    assert supports_provider_runtime("ollama") is True
    assert supports_provider_runtime("lmstudio") is True
    monkeypatch.setenv("UAGENT_LMSTUDIO_TRANSPORT", "sdk")
    assert supports_provider_runtime("lmstudio") is False
    assert supports_provider_runtime("meta") is True
    assert supports_provider_runtime("") is False
