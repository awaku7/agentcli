"""Provider-independent selection of the active round implementation.

The round loop still has to support the incremental migration from the
legacy provider handlers to ``ProviderRuntimeRegistry``. Keeping that
selection in this module prevents the orchestration loop from knowing the
order or shape of the fallback implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from .round_contracts import RoundTransportSelection

DispatchSource = Literal["registry", "legacy", "openai_compatible"]
RoundRunner = Callable[..., Any]
RegistryLegacyResult = tuple[bool, str, str, list[dict[str, Any]]]


def registry_tuple_to_outcome(result: Any, provider: str) -> Any:
    """Normalize a registry compatibility tuple to ``LegacyRoundOutcome``."""
    from .legacy_round_registry import (
        LegacyRoundOutcome,
        RoundOutcomeCapabilities,
    )
    from .round_contracts import RoundSummary

    if isinstance(result, LegacyRoundOutcome):
        return result
    if not isinstance(result, tuple) or len(result) != 4:
        return None
    ok, assistant_text, reasoning_text, tool_calls = result
    normalized_tool_calls = tuple(tool_calls or ())
    return LegacyRoundOutcome(
        provider=(provider or "").strip().lower(),
        status="ok" if ok else "return",
        assistant_text=str(assistant_text or ""),
        raw_result=result,
        reasoning_text=str(reasoning_text or ""),
        tool_calls=normalized_tool_calls,
        summary=RoundSummary(
            status="completed" if ok else "failed",
            tool_call_count=len(normalized_tool_calls),
            assistant_chars=len(str(assistant_text or "")),
            reasoning_chars=len(str(reasoning_text or "")),
        ),
        capabilities=RoundOutcomeCapabilities(
            handles_collected_result=True,
            supports_tool_continuation=bool(tool_calls),
        ),
        flow="registry",
    )


def _dispatch_outcome(source: DispatchSource, result: Any, provider: str) -> Any:
    """Return a shared outcome view without changing ``result``."""
    if source == "registry":
        return registry_tuple_to_outcome(result, provider)
    from .legacy_round_registry import LegacyRoundOutcome

    return result if isinstance(result, LegacyRoundOutcome) else None


def registry_result_to_legacy_tuple(result: Any) -> RegistryLegacyResult | None:
    """Adapt a completed registry ``RoundResult`` to the legacy loop shape.

    The compatibility loop still consumes ``(ok, text, reasoning, tools)``.
    Keeping this conversion at the dispatcher boundary prevents provider-neutral
    result details from leaking into the loop while legacy adapters migrate.
    """

    if getattr(result, "status", None) != "completed":
        return None
    assistant_text = str(getattr(result, "assistant_text", "") or "")
    reasoning_text = str(getattr(result, "reasoning_text", "") or "")
    raw_tool_calls = getattr(result, "tool_calls", ()) or ()
    if (
        not assistant_text
        and not raw_tool_calls
        and not getattr(result, "continuation_update", {})
    ):
        return None

    normalized_tool_calls: list[dict[str, Any]] = []
    for call in raw_tool_calls:
        item = dict(call)
        function = item.get("function")
        if not isinstance(function, dict):
            function = {
                "name": str(item.get("name") or ""),
                "arguments": str(item.get("arguments") or "{}"),
            }
            item["function"] = function
        item.setdefault(
            "id", str(item.get("tool_call_id") or item.get("call_id") or "")
        )
        item.setdefault("type", "function")
        normalized_tool_calls.append(item)
    return True, assistant_text, reasoning_text, normalized_tool_calls


@dataclass(frozen=True)
class RegistryRoundRoute:
    """Resolved registry eligibility passed to the round dispatcher."""

    allowed: bool
    reason: str = ""


def resolve_registry_round_route(
    *,
    provider: str,
    configured_providers: str = "",
    use_responses_api: bool,
    responses_enabled: bool,
    send_tools: bool,
    tools_enabled: bool,
    has_context_tools: bool,
    uses_legacy_catalog: bool,
    transport_selection: RoundTransportSelection | None = None,
) -> RegistryRoundRoute:
    """Resolve registry eligibility once for a provider round."""

    from ..providers.runtime_registry import supports_provider_runtime

    if transport_selection is not None:
        use_responses_api = transport_selection.use_responses_api

    if not supports_provider_runtime(provider):
        return RegistryRoundRoute(False, "unsupported_provider")
    configured = (configured_providers or "").strip().lower()
    if configured in {"0", "false", "no", "off"}:
        return RegistryRoundRoute(False, "disabled_by_configuration")
    enabled_providers = {item.strip() for item in configured.split(",") if item.strip()}
    if (
        configured
        and provider.strip().lower() not in enabled_providers
        and "all" not in enabled_providers
    ):
        return RegistryRoundRoute(False, "provider_not_enabled")
    if use_responses_api and not responses_enabled:
        return RegistryRoundRoute(False, "responses_registry_disabled")
    if uses_legacy_catalog:
        return RegistryRoundRoute(False, "legacy_catalog_conflict")
    if send_tools and not tools_enabled:
        return RegistryRoundRoute(False, "tools_registry_disabled")
    if send_tools and not has_context_tools:
        return RegistryRoundRoute(False, "context_tools_missing")
    return RegistryRoundRoute(True, "eligible")


def registry_round_allowed(**kwargs: Any) -> bool:
    """Backward-compatible boolean view of ``resolve_registry_round_route``."""

    return resolve_registry_round_route(**kwargs).allowed


@dataclass(frozen=True)
class ProviderRoundDispatch:
    """The selected implementation and its provider-specific result."""

    source: DispatchSource
    result: Any
    outcome: Any = None

    @property
    def handles_collected_result(self) -> bool:
        return bool(
            self.outcome is not None
            and self.outcome.capabilities.handles_collected_result
        )

    @property
    def owns_tool_execution(self) -> bool:
        return bool(
            self.outcome is not None
            and self.outcome.capabilities.owns_tool_execution
        )

    @property
    def supports_tool_continuation(self) -> bool:
        return bool(
            self.outcome is not None
            and self.outcome.capabilities.supports_tool_continuation
        )

    @property
    def host_rendered(self) -> bool:
        return bool(
            self.outcome is not None
            and self.outcome.capabilities.host_rendered
        )


def dispatch_provider_round(
    *,
    registry_runner: RoundRunner | None,
    registry_allowed: bool = True,
    registry_route: RegistryRoundRoute | None = None,
    legacy_runner: RoundRunner,
    openai_runner: RoundRunner,
    registry_kwargs: Mapping[str, Any],
    legacy_kwargs: Mapping[str, Any],
    openai_kwargs: Mapping[str, Any],
) -> ProviderRoundDispatch:
    """Select the first applicable round implementation.

    ``registry_route`` is the resolved route contract and takes precedence
    over the boolean compatibility flag. ``registry_allowed=False`` disables
    only the registry candidate and keeps the compatibility order intact.
    ``None`` from a runner means that the
    runner does not own the current provider/mode and the next compatibility
    path should be tried. A non-``None`` result is returned unchanged,
    including falsy tuple values, so this helper does not reinterpret provider
    behavior.
    """

    if registry_route is not None:
        registry_allowed = registry_route.allowed
    if registry_allowed and registry_runner is not None:
        registry_result = registry_runner(**dict(registry_kwargs))
        if registry_result is not None:
            return ProviderRoundDispatch(
                "registry",
                registry_result,
                _dispatch_outcome(
                    "registry",
                    registry_result,
                    str(registry_kwargs.get("provider") or ""),
                ),
            )

    legacy_result = legacy_runner(**dict(legacy_kwargs))
    if legacy_result is not None:
        return ProviderRoundDispatch(
            "legacy",
            legacy_result,
            _dispatch_outcome(
                "legacy",
                legacy_result,
                str(legacy_kwargs.get("provider") or ""),
            ),
        )

    openai_result = openai_runner(**dict(openai_kwargs))
    return ProviderRoundDispatch(
        "openai_compatible",
        openai_result,
        _dispatch_outcome(
            "openai_compatible",
            openai_result,
            str(openai_kwargs.get("provider") or ""),
        ),
    )


__all__ = [
    "DispatchSource",
    "ProviderRoundDispatch",
    "RegistryLegacyResult",
    "RegistryRoundRoute",
    "dispatch_provider_round",
    "registry_result_to_legacy_tuple",
    "registry_tuple_to_outcome",
    "registry_round_allowed",
    "resolve_registry_round_route",
]
