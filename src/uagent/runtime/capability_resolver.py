"""A conservative, inspectable capability snapshot for one LLM route.

This module deliberately does *not* replace existing provider checks yet.  It
is the boundary that lets the round runtime ask one question about a route
without moving provider-specific decisions back into the orchestration loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from ..llmcapa_util import provider_allows_responses_api, supports_feature
from ..providers.provider_caps import DEFAULT_PROVIDER_REGISTRY, ProviderRegistry
from ..providers.responses_manager import get_responses_capabilities


class CapabilityState(str, Enum):
    """Evidence state for a native feature.

    ``UNKNOWN`` is intentionally not permission to use a native feature.
    Callers that need a Boolean decision must use :meth:`is_native_allowed`.
    """

    TRUE_DOCUMENTED = "true_documented"
    TRUE_TESTED = "true_tested"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CapabilityValue:
    state: CapabilityState
    source: str

    def is_native_allowed(self) -> bool:
        """Whether it is safe to select the native implementation."""
        return self.state in {
            CapabilityState.TRUE_DOCUMENTED,
            CapabilityState.TRUE_TESTED,
        }


@dataclass(frozen=True)
class ProviderCapabilitySnapshot:
    """Capabilities resolved for a provider/model/transport tuple."""

    provider: str
    model: str
    transport: str
    streaming: CapabilityValue
    tools: CapabilityValue
    vision: CapabilityValue
    responses_create: CapabilityValue
    responses_streaming: CapabilityValue
    responses_continuation: CapabilityValue
    responses_compact: CapabilityValue
    structured_output: CapabilityValue
    tool_search: CapabilityValue


class CapabilityResolverPort(Protocol):
    """Read-only capability lookup consumed by provider adapters."""

    def resolve(
        self, provider: str, model: str = "", transport: str = "chat_completions"
    ) -> ProviderCapabilitySnapshot: ...


class CapabilityResolver:
    """Build a read-only snapshot from the current capability sources.

    The static provider registry supplies implementation support. ``llmcapa``
    may narrow that support for a model.  Absent model evidence remains
    ``UNKNOWN`` rather than being silently upgraded to native support.
    """

    def __init__(
        self,
        registry: ProviderRegistry = DEFAULT_PROVIDER_REGISTRY,
        feature_lookup: Callable[[str, str, str], bool | None] | None = None,
    ) -> None:
        self._registry = registry
        self._feature_lookup = feature_lookup or self._lookup_feature

    @staticmethod
    def _lookup_feature(feature: str, model: str, provider: str) -> bool | None:
        return supports_feature(feature, model, provider, default=None)

    @staticmethod
    def _static(value: bool, source: str) -> CapabilityValue:
        return CapabilityValue(
            CapabilityState.TRUE_TESTED if value else CapabilityState.FALSE,
            source,
        )

    def _model_feature(
        self,
        feature: str,
        provider: str,
        model: str,
        *,
        implemented: bool,
        source: str,
    ) -> CapabilityValue:
        if not implemented:
            return self._static(False, source)
        value = self._feature_lookup(feature, model, provider) if model else None
        if value is True:
            return CapabilityValue(CapabilityState.TRUE_DOCUMENTED, "llmcapa")
        if value is False:
            return CapabilityValue(CapabilityState.FALSE, "llmcapa")
        return CapabilityValue(CapabilityState.UNKNOWN, source)

    def resolve(
        self, provider: str, model: str = "", transport: str = "chat_completions"
    ) -> ProviderCapabilitySnapshot:
        """Resolve capabilities without changing routing or fallback behaviour."""
        spec = self._registry.resolve(provider, model)
        normalized_model = (model or "").strip()
        responses = get_responses_capabilities(spec.name)
        responses_implemented = "responses" in spec.capabilities
        return ProviderCapabilitySnapshot(
            provider=spec.name,
            model=normalized_model,
            transport=(transport or "chat_completions").strip().lower(),
            streaming=self._model_feature(
                "streaming",
                spec.name,
                normalized_model,
                implemented=spec.supports_streaming,
                source="provider_registry",
            ),
            tools=self._model_feature(
                "function_calling",
                spec.name,
                normalized_model,
                implemented=spec.supports_tools,
                source="provider_registry",
            ),
            vision=self._model_feature(
                "vision",
                spec.name,
                normalized_model,
                implemented=spec.supports_vision,
                source="provider_registry",
            ),
            responses_create=self._model_feature(
                "responses_api",
                spec.name,
                normalized_model,
                implemented=responses_implemented and responses.create,
                source="responses_manager",
            ),
            responses_streaming=self._static(
                responses_implemented and responses.streaming, "responses_manager"
            ),
            responses_continuation=self._static(
                responses_implemented and responses.previous_response_id,
                "responses_manager",
            ),
            responses_compact=self._static(
                responses_implemented and responses.compact, "responses_manager"
            ),
            structured_output=self._model_feature(
                "json_schema",
                spec.name,
                normalized_model,
                implemented=True,
                source="llmcapa",
            ),
            tool_search=self._model_feature(
                "tool_search",
                spec.name,
                normalized_model,
                implemented=responses_implemented and responses.create,
                source="llmcapa",
            ),
        )


def _resolver_or_none(
    resolver: CapabilityResolverPort | None,
) -> CapabilityResolverPort | None:
    if resolver is not None:
        return resolver
    try:
        return CapabilityResolver()
    except Exception:
        return None


def responses_api_auto_enabled(
    provider: str,
    model: str = "",
    *,
    resolver: CapabilityResolverPort | None = None,
) -> bool:
    """Return whether automatic routing may select the Responses API.

    Automatic selection is deliberately conservative: missing catalog evidence
    and resolver failures are not permission to select a native provider
    surface.
    """

    capability_resolver = _resolver_or_none(resolver)
    if capability_resolver is None:
        return False

    try:
        snapshot = capability_resolver.resolve(
            provider,
            model or "",
            transport="responses",
        )
    except Exception:
        return False
    return snapshot.responses_create.is_native_allowed()


def responses_api_explicit_enabled(
    provider: str,
    model: str = "",
    *,
    resolver: CapabilityResolverPort | None = None,
) -> bool:
    """Return whether an explicit Responses request may use that transport.

    Explicit opt-in preserves the historical fail-open behavior when model
    evidence is unknown, but an explicit llmcapa/provider implementation
    ``False`` is authoritative.  This keeps user intent compatible while
    preventing requests from being sent to a transport known not to exist for
    the selected provider/model.
    """

    capability_resolver = _resolver_or_none(resolver)
    if capability_resolver is not None:
        try:
            snapshot = capability_resolver.resolve(
                provider,
                model or "",
                transport="responses",
            )
            if snapshot.responses_create.state is CapabilityState.FALSE:
                return False
            if snapshot.responses_create.is_native_allowed():
                return True
        except Exception:
            pass

    # UNKNOWN/resolver failure: retain the legacy explicit-opt-in behavior,
    # while still respecting provider implementation support and any llmcapa
    # false value available through the shared compatibility helper.
    try:
        return provider_allows_responses_api(provider, model)
    except Exception:
        return False


def streaming_requested_enabled(
    provider: str,
    model: str = "",
    *,
    requested: bool,
    transport: str = "chat_completions",
    resolver: CapabilityResolverPort | None = None,
) -> bool:
    """Narrow a requested streaming mode using provider/model capability data.

    Unknown model evidence preserves the requested setting for compatibility;
    an explicit model/provider ``False`` disables streaming.
    """

    if not requested:
        return False
    capability_resolver = _resolver_or_none(resolver)
    if capability_resolver is None:
        return True
    try:
        snapshot = capability_resolver.resolve(
            provider,
            model or "",
            transport=transport,
        )
    except Exception:
        return True
    return snapshot.streaming.state is not CapabilityState.FALSE


def structured_output_native_enabled(
    provider: str,
    model: str = "",
    *,
    resolver: CapabilityResolverPort | None = None,
) -> bool:
    """Return whether native structured output has positive model evidence.

    JSON Schema support is preferred, but JSON Object mode is also sufficient
    for requests that do not carry a schema. This keeps the capability gate
    aligned with the provider adapter, which may legitimately select either
    native representation.
    """
    if resolver is None:
        try:
            # Keep the default path aligned with the provider adapters' exact
            # llmcapa helpers (and with their tri-state semantics).
            from .. import llmcapa_util

            model_id = model or ""
            return (
                llmcapa_util.supports_json_schema(model_id, provider) is True
                or llmcapa_util.supports_json_mode(model_id, provider) is True
            )
        except Exception:
            return False

    capability_resolver = resolver
    model_id = model or ""
    try:
        snapshot = capability_resolver.resolve(
            provider,
            model_id,
            transport="chat_completions",
        )
        if snapshot.structured_output.is_native_allowed():
            return True
    except Exception:
        return False

    # The snapshot currently exposes the stricter JSON Schema capability.
    # Query JSON Object evidence separately so schema-less requests are not
    # rejected merely because the model only advertises JSON mode.
    feature_lookup = getattr(capability_resolver, "_feature_lookup", None)
    if not callable(feature_lookup):
        return False
    try:
        return feature_lookup("json_mode", model_id, provider) is True
    except Exception:
        return False


def native_structured_output_request_for_runtime(
    messages: list[dict[str, object]],
    *,
    provider: str,
    model: str = "",
    model_id: str | None = None,
    resolver: CapabilityResolverPort | None = None,
) -> dict[str, object] | None:
    """Build native structured output only after capability authorization."""
    resolved_model = model if model_id is None else model_id
    if not structured_output_native_enabled(
        provider, resolved_model, resolver=resolver
    ):
        return None

    if resolver is None:
        # Preserve the provider adapter's exact native representation (schema
        # versus JSON Object) after the runtime gate has authorized it.
        from ..providers.structured_output import native_structured_output_request

        return native_structured_output_request(
            messages, model_id=resolved_model, provider=provider
        )

    # Injected resolvers are used by characterization tests and higher-level
    # runtime callers; their positive evidence authorizes the normalized
    # request without consulting the global catalog a second time.
    from ..providers.structured_output import structured_output_request

    return structured_output_request(messages)
