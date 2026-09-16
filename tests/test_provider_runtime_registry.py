from __future__ import annotations

from types import SimpleNamespace

import pytest

from uagent.providers.inception_runtime import InceptionProviderRuntime
from uagent.providers.openai_compatible_runtime import OpenAICompatibleRuntime
from uagent.providers.runtime_registry import build_provider_runtime_registry
from uagent.runtime.round_contracts import RoundIdentifiers


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1)


def test_registry_builds_openai_and_azure_compatible_adapters() -> None:
    for provider in ("openai", "azure"):
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
