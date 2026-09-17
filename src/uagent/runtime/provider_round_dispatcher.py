"""Provider-independent selection of the active round implementation.

The round loop still has to support the incremental migration from the
legacy provider handlers to ``ProviderRuntimeRegistry``. Keeping that
selection in this module prevents the orchestration loop from knowing the
order or shape of the fallback implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

DispatchSource = Literal["registry", "legacy", "openai_compatible"]
RoundRunner = Callable[..., Any]


def registry_round_allowed(
    *,
    provider: str,
    configured_providers: str = "",
    use_responses_api: bool,
    responses_enabled: bool,
    send_tools: bool,
    tools_enabled: bool,
    has_context_tools: bool,
    uses_legacy_catalog: bool,
) -> bool:
    """Return whether the registry may own the current round.

    This gate contains only route-selection policy. Adapter execution failures
    are still handled by ``dispatch_provider_round`` and may fall back to the
    compatibility handlers. The supported-provider source remains the runtime
    registry itself, so this module does not maintain a second provider list.
    """

    from ..providers.runtime_registry import supports_provider_runtime

    if not supports_provider_runtime(provider):
        return False
    configured = (configured_providers or "").strip().lower()
    if configured in {"0", "false", "no", "off"}:
        return False
    enabled_providers = {item.strip() for item in configured.split(",") if item.strip()}
    if configured and provider.strip().lower() not in enabled_providers and "all" not in enabled_providers:
        return False
    if use_responses_api and not responses_enabled:
        return False
    if uses_legacy_catalog:
        return False
    if send_tools and not tools_enabled:
        return False
    if send_tools and not has_context_tools:
        return False
    return True


@dataclass(frozen=True)
class ProviderRoundDispatch:
    """The selected implementation and its provider-specific result."""

    source: DispatchSource
    result: Any


def dispatch_provider_round(
    *,
    registry_runner: RoundRunner | None,
    legacy_runner: RoundRunner,
    openai_runner: RoundRunner,
    registry_kwargs: Mapping[str, Any],
    legacy_kwargs: Mapping[str, Any],
    openai_kwargs: Mapping[str, Any],
) -> ProviderRoundDispatch:
    """Select the first applicable round implementation.

    ``None`` from a runner means that the runner does not own the current
    provider/mode and the next compatibility path should be tried. A
    non-``None`` result is returned unchanged, including falsy tuple values,
    so this helper does not reinterpret provider behavior.
    """

    if registry_runner is not None:
        registry_result = registry_runner(**dict(registry_kwargs))
        if registry_result is not None:
            return ProviderRoundDispatch("registry", registry_result)

    legacy_result = legacy_runner(**dict(legacy_kwargs))
    if legacy_result is not None:
        return ProviderRoundDispatch("legacy", legacy_result)

    return ProviderRoundDispatch(
        "openai_compatible", openai_runner(**dict(openai_kwargs))
    )


__all__ = [
    "DispatchSource",
    "ProviderRoundDispatch",
    "dispatch_provider_round",
    "registry_round_allowed",
]
