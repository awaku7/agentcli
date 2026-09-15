"""Construction helpers for the incremental provider runtime registry."""

from __future__ import annotations

from typing import Any, Mapping

from ..runtime.round_contracts import (
    ProviderRuntimeRegistry,
    RoundIdentifiers,
)
from .inception_runtime import InceptionProviderRuntime
from .openai_compatible_runtime import OpenAICompatibleRuntime

_SUPPORTED = frozenset({"inception", "openai", "azure"})


def build_provider_runtime_registry(
    *,
    provider: str,
    client: Any,
    model: str,
    identifiers: RoundIdentifiers,
    transport: str = "chat_completions",
    options: Mapping[str, Any] | None = None,
) -> ProviderRuntimeRegistry:
    """Build a registry for one migrated provider family.

    Providers outside the migrated set are deliberately rejected rather than
    silently routed through a partially compatible adapter. Their legacy path
    remains the caller's responsibility until a dedicated runtime is added.
    """
    provider_key = (provider or "").strip().lower()
    if provider_key not in _SUPPORTED:
        raise ValueError(
            f"provider runtime is not migrated: {provider_key or '<empty>'}"
        )

    if provider_key == "inception":
        runtime = InceptionProviderRuntime(
            client=client,
            model=model,
            identifiers=identifiers,
            options=options,
        )
    else:
        runtime = OpenAICompatibleRuntime(
            client=client,
            provider=provider_key,
            model=model,
            identifiers=identifiers,
            transport=transport,
            options=options,
        )

    registry = ProviderRuntimeRegistry()
    registry.register(provider_key, runtime)
    return registry


__all__ = ["build_provider_runtime_registry"]
