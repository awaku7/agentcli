"""Construction helpers for the incremental provider runtime registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from ..env_utils import env_get

if TYPE_CHECKING:
    from ..runtime.capability_resolver import CapabilityResolverPort

from ..runtime.round_contracts import (
    ProviderRuntimeRegistry,
    RoundIdentifiers,
    RoundTransportSelection,
)
from .grok_runtime import GrokGrpcProviderRuntime
from .inception_runtime import InceptionProviderRuntime
from .openai_compatible_runtime import OpenAICompatibleRuntime
from .pfn_runtime import PfnProviderRuntime

_SUPPORTED = frozenset(
    {
        "inception",
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
        "pfn",
        "grok",
    }
)


def supports_provider_runtime(provider: str) -> bool:
    """Return whether the incremental runtime registry owns ``provider``.

    This is the single eligibility check for callers that must decide whether
    to enter the registry path. Keeping it next to the registry's supported
    set avoids duplicating a provider allow-list in the round loop.
    """

    provider_key = (provider or "").strip().lower()
    if provider_key == "lmstudio":
        transport = (env_get("UAGENT_LMSTUDIO_TRANSPORT", "") or "").strip().lower()
        return transport != "sdk" and provider_key in _SUPPORTED
    return provider_key in _SUPPORTED


def build_provider_runtime_registry(
    *,
    provider: str,
    client: Any,
    model: str,
    identifiers: RoundIdentifiers,
    transport: str = "chat_completions",
    streaming: bool = True,
    options: Mapping[str, Any] | None = None,
    capability_resolver: CapabilityResolverPort | None = None,
    transport_selection: RoundTransportSelection | None = None,
) -> ProviderRuntimeRegistry:
    """Build a registry for one migrated provider family.

    Providers outside the migrated set are deliberately rejected rather than
    silently routed through a partially compatible adapter. Their legacy path
    remains the caller's responsibility until a dedicated runtime is added.
    """
    provider_key = (provider or "").strip().lower()
    if not supports_provider_runtime(provider_key):
        raise ValueError(
            f"provider runtime is not migrated: {provider_key or '<empty>'}"
        )

    if transport_selection is not None:
        transport = transport_selection.transport
        streaming = transport_selection.streaming

    if provider_key == "inception":
        runtime = InceptionProviderRuntime(
            client=client,
            model=model,
            identifiers=identifiers,
            options=options,
            capability_resolver=capability_resolver,
        )
    elif provider_key == "grok":
        runtime = GrokGrpcProviderRuntime(
            client=client,
            provider=provider_key,
            model=model,
            identifiers=identifiers,
            transport=transport,
            streaming=streaming,
            options=options,
            capability_resolver=capability_resolver,
        )
    elif provider_key == "pfn":
        runtime = PfnProviderRuntime(
            client=client,
            provider=provider_key,
            model=model,
            identifiers=identifiers,
            transport=transport,
            streaming=streaming,
            options=options,
            capability_resolver=capability_resolver,
        )
    else:
        runtime = OpenAICompatibleRuntime(
            client=client,
            provider=provider_key,
            model=model,
            identifiers=identifiers,
            transport=transport,
            streaming=streaming,
            options=options,
            capability_resolver=capability_resolver,
        )

    registry = ProviderRuntimeRegistry()
    registry.register(provider_key, runtime)
    return registry


__all__ = ["build_provider_runtime_registry", "supports_provider_runtime"]
