"""Provider-neutral boundaries for discovering, selecting, and delivering tools.

Tool origin is metadata, not a delivery decision: MCP/A2A/skills may have
different permission and invocation paths even when their schemas look alike.
Keeping these phases separate prevents the LLM round loop from becoming a tool
catalog again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Protocol

if TYPE_CHECKING:
    from .capability_resolver import CapabilityResolverPort


class ToolSource(str, Enum):
    BUILTIN = "builtin"
    MCP = "mcp"
    SKILL = "skill"
    A2A = "a2a"
    PROVIDER_NATIVE = "provider_native"


class ToolDeliveryMode(str, Enum):
    LOADED_SPECS = "loaded_specs"
    MANAGEMENT_TOOLS = "management_tools"
    PROVIDER_NATIVE_SEARCH = "provider_native_search"


class ToolDiscoveryMode(str, Enum):
    """Provider-facing decision for how tools are discovered and delivered."""

    SELECTED_SCHEMAS = "selected_schemas"
    LEGACY_CATALOG = "legacy_catalog"
    NATIVE_SEARCH = "native_search"


MANAGEMENT_TOOL_NAMES = frozenset({"tool_catalog", "tool_load", "unload_tool"})


def provider_messages_api_enabled(provider: str | None) -> bool:
    """Return whether an explicitly selected Anthropic Messages route is active.

    OpenRouter and DeepSeek use OpenAI-compatible clients by default. Their
    Messages endpoints are opt-in so merely adding a Messages capability to
    llmcapa cannot silently change the API used by an existing installation.
    """
    provider_name = (provider or "").strip().lower()
    env_names = {
        "openrouter": "UAGENT_OPENROUTER_API",
        "deepseek": "UAGENT_DEEPSEEK_API",
    }
    env_name = env_names.get(provider_name)
    if not env_name:
        return provider_name in {"claude", "anthropic"}
    try:
        from ..env_utils import env_get

        value = (env_get(env_name) or "").strip().lower()
    except Exception:
        return False
    return value in {"messages", "anthropic", "anthropic_messages"}


@dataclass(frozen=True)
class ToolDiscoveryDecision:
    """The single discovery decision shared by round and command paths."""

    mode: ToolDiscoveryMode
    reason: str

    @property
    def uses_native_search(self) -> bool:
        return self.mode is ToolDiscoveryMode.NATIVE_SEARCH

    @property
    def uses_legacy_catalog(self) -> bool:
        return self.mode is ToolDiscoveryMode.LEGACY_CATALOG

    @property
    def uses_selected_schemas(self) -> bool:
        return self.mode is ToolDiscoveryMode.SELECTED_SCHEMAS

    def uses_management_bootstrap(self, *, use_responses_api: bool) -> bool:
        """Return whether bootstrap should expose management catalog tools."""

        return self.uses_legacy_catalog or (
            self.uses_native_search and not use_responses_api
        )

    def needs_catalog_steering(self) -> bool:
        """Return whether prompts should steer the model to tool_catalog."""

        return not self.uses_native_search


def get_tool_search_mode(raw: str | None = None, *, provider: str | None = None) -> str:
    """Normalize the user-facing native tool-search mode setting.

    OpenRouter and DeepSeek have separate switches because their provider
    protocols differ from the OpenAI GPT-5.4 tool-search mode.
    """

    if raw is None:
        try:
            from ..env_utils import env_get

            env_name = (
                "UAGENT_OPENROUTER_TOOL_SEARCH"
                if (provider or "").strip().lower() == "openrouter"
                else (
                    "UAGENT_DEEPSEEK_TOOL_SEARCH"
                    if (provider or "").strip().lower() == "deepseek"
                    else "UAGENT_GPT54_TOOL_SEARCH"
                )
            )
            raw = env_get(env_name)
        except Exception:
            raw = None
    value = (raw or "").strip().lower()
    if value in {"legacy", "old"}:
        return "legacy"
    if value in {"off", "0", "false", "no"}:
        return "off"
    return "native"


def gemini_interactions_tool_retrieval_enabled(
    provider: str | None, depname: str | None
) -> bool:
    """Return True only when llmcapa documents Gemini Interactions retrieval.

    Gemini's Interactions API uses the same ``tool_search`` capability name as
    other provider APIs, but its transport and request format are different.
    Keep this gate separate from the Responses API discovery decision below.
    Unknown capability data is deliberately treated as unsupported.
    """
    provider_name = (provider or "").strip().lower()
    model_name = (depname or "").strip()
    if provider_name not in {"gemini", "vertexai", "vertex-ai", "google"}:
        return False
    if not model_name:
        return False
    try:
        from ..providers.gemini_api_mode import gemini_api_mode

        if gemini_api_mode(model_name, provider_name) != "interactions":
            return False
    except Exception:
        return False
    try:
        from ..llmcapa_util import get_capability, supports_feature

        feature_value = supports_feature(
            "tool_search", model_name, provider_name, default=None
        )
        if feature_value is not None:
            return feature_value is True
        # Some llmcapa releases expose this provider-native field directly
        # before including it in Capability.supports().
        capability = get_capability(model_name, provider_name)
        return getattr(capability, "supports_tool_search", None) is True
    except Exception:
        return False


def anthropic_messages_tool_search_variant(
    provider: str | None,
    depname: str | None,
    *,
    configured_mode: str | None = None,
) -> str | None:
    """Return a documented Anthropic Messages search variant, if supported.

    This is deliberately separate from the Responses and Gemini Interactions
    routes: Anthropic's Messages API has its own server-tool names and requires
    the complete tool catalog with ``defer_loading`` on deferred definitions.
    Unknown llmcapa details fail closed rather than inferring support from a
    model name.
    """
    provider_name = (provider or "").strip().lower()
    if provider_name not in {"claude", "openrouter"}:
        return None
    model_name = (depname or "").strip()
    if not model_name:
        return None

    if configured_mode is None and provider_name == "claude":
        try:
            from ..env_utils import env_get

            configured_mode = env_get("UAGENT_ANTHROPIC_TOOL_SEARCH")
        except Exception:
            configured_mode = None
    raw_mode = (configured_mode or "").strip().lower()
    requested_variant = raw_mode if raw_mode in {"bm25", "regex"} else None
    mode = get_tool_search_mode(configured_mode, provider=provider_name)
    if mode in {"off", "0", "false", "no", "legacy", "old"}:
        return None
    if mode not in {"", "native", "auto"}:
        return None

    try:
        from ..llmcapa_util import get_capability, supports_feature

        if (
            supports_feature("tool_search", model_name, provider_name, default=None)
            is not True
        ):
            return None
        capability = get_capability(model_name, provider_name)
        details = getattr(capability, "tool_search", None)
        if isinstance(details, dict):
            execution = details.get("execution")
            surfaces = details.get("api_surfaces")
            variants = details.get("variants")
        else:
            execution = getattr(details, "execution", None)
            surfaces = getattr(details, "api_surfaces", None)
            variants = getattr(details, "variants", None)
        if not details:
            return None

        def _values(value: Any) -> set[str]:
            if isinstance(value, str):
                return {value.strip().lower()}
            if isinstance(value, (tuple, list, set, frozenset)):
                return {str(item).strip().lower() for item in value}
            return set()

        if "server" not in _values(execution) or "messages" not in _values(surfaces):
            return None
        available = _values(variants)
        if provider_name == "openrouter":
            # OpenRouter's Messages alias is regex-only, even if the upstream
            # model also advertises an Anthropic BM25 implementation.
            return "regex" if "regex" in available else None
        if requested_variant is not None:
            return requested_variant if requested_variant in available else None
        if "bm25" in available:
            return "bm25"
        if "regex" in available:
            return "regex"
    except Exception:
        return None


def openrouter_responses_tool_search_variant(
    provider: str | None,
    depname: str | None,
    *,
    configured_mode: str | None = None,
) -> str | None:
    """Return OpenRouter's documented Responses server-tool variant, if allowed."""
    if (provider or "").strip().lower() != "openrouter":
        return None
    model_name = (depname or "").strip()
    if not model_name:
        return None
    if get_tool_search_mode(configured_mode, provider="openrouter") != "native":
        return None

    try:
        from ..llmcapa_util import get_capability, supports_feature

        if (
            supports_feature("tool_search", model_name, "openrouter", default=None)
            is not True
        ):
            return None
        capability = get_capability(model_name, "openrouter")
        detail = getattr(capability, "tool_search", None)
        if detail is None:
            return None

        def values(name: str) -> set[str]:
            value = (
                detail.get(name)
                if isinstance(detail, Mapping)
                else getattr(detail, name, None)
            )
            if isinstance(value, str):
                return {value.strip().lower()}
            if isinstance(value, (tuple, list, set, frozenset)):
                return {str(item).strip().lower() for item in value}
            return set()

        if "server" not in values("execution"):
            return None
        if "responses" not in values("api_surfaces"):
            return None
        if "regex" not in values("variants"):
            return None
        return "regex"
    except Exception:
        return None
    return None


def deepseek_messages_tool_search_enabled(
    provider: str | None,
    depname: str | None,
    *,
    configured_mode: str | None = None,
) -> bool:
    """Return True for DeepSeek Flash's client-executed Messages deferral."""
    if (provider or "").strip().lower() != "deepseek":
        return False
    model_name = (depname or "").strip()
    if not model_name or not provider_messages_api_enabled("deepseek"):
        return False
    if get_tool_search_mode(configured_mode, provider="deepseek") != "native":
        return False
    try:
        from ..env_utils import env_get

        if (env_get("UAGENT_EMBEDDED") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        from .execution_broker import current_sandbox_enabled

        if current_sandbox_enabled():
            return False
    except Exception:
        pass

    try:
        from ..llmcapa_util import get_capability, supports_feature

        if (
            supports_feature("tool_search", model_name, "deepseek", default=None)
            is not True
        ):
            return False
        capability = get_capability(model_name, "deepseek")
        detail = getattr(capability, "tool_search", None)
        if detail is None:
            return False

        def values(name: str) -> set[str]:
            value = (
                detail.get(name)
                if isinstance(detail, Mapping)
                else getattr(detail, name, None)
            )
            if isinstance(value, str):
                return {value.strip().lower()}
            if isinstance(value, (tuple, list, set, frozenset)):
                return {str(item).strip().lower() for item in value}
            return set()

        return "client" in values("execution") and "messages" in values("api_surfaces")
    except Exception:
        return False


def deepseek_responses_tool_search_enabled(
    provider: str | None,
    depname: str | None,
    *,
    configured_mode: str | None = None,
) -> bool:
    """Return True for DeepSeek's client-executed Responses tool search."""
    if (provider or "").strip().lower() != "deepseek":
        return False
    model_name = (depname or "").strip()
    if not model_name:
        return False
    if get_tool_search_mode(configured_mode, provider="deepseek") != "native":
        return False
    try:
        from ..env_utils import env_get

        if (env_get("UAGENT_EMBEDDED") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        from .execution_broker import current_sandbox_enabled

        if current_sandbox_enabled():
            return False
    except Exception:
        # The ordinary non-sandbox route is still resolved from model metadata
        # when the optional host execution policy is unavailable.
        pass

    try:
        from ..llmcapa_util import get_capability, supports_feature

        if (
            supports_feature("tool_search", model_name, "deepseek", default=None)
            is not True
        ):
            return False
        capability = get_capability(model_name, "deepseek")
        detail = getattr(capability, "tool_search", None)
        if detail is None:
            return False

        def values(name: str) -> set[str]:
            value = (
                detail.get(name)
                if isinstance(detail, Mapping)
                else getattr(detail, name, None)
            )
            if isinstance(value, str):
                return {value.strip().lower()}
            if isinstance(value, (tuple, list, set, frozenset)):
                return {str(item).strip().lower() for item in value}
            return set()

        return "client" in values("execution") and "responses" in values("api_surfaces")
    except Exception:
        return False


def anthropic_messages_tool_search_variant_from_environment() -> str | None:
    """Resolve Anthropic Messages tool search for the active provider/model."""
    try:
        from ..env_utils import env_get
        from ..llmcapa_util import current_model

        provider = (env_get("UAGENT_PROVIDER") or "").strip().lower()
        model = current_model(provider) if provider else ""
        if provider == "openrouter" and not provider_messages_api_enabled(provider):
            return None
        return anthropic_messages_tool_search_variant(provider, model)
    except Exception:
        return None


def gemini_interactions_tool_retrieval_enabled_from_environment() -> bool:
    """Resolve Gemini tool retrieval from the active provider/model settings."""
    try:
        from ..env_utils import env_get
        from ..llmcapa_util import current_model

        provider = (env_get("UAGENT_PROVIDER") or "").strip().lower()
        if not provider:
            return False
        model = current_model(provider)
        return gemini_interactions_tool_retrieval_enabled(provider, model)
    except Exception:
        return False


def resolve_tool_discovery_from_environment(
    *,
    provider: str | None = None,
    depname: str | None = None,
    use_responses_api: bool | None = None,
    capability_resolver: CapabilityResolverPort | None = None,
) -> ToolDiscoveryDecision:
    """Resolve discovery using the common environment policy.

    Callers may provide values already resolved by a round. When omitted,
    this function reads only discovery-related settings and does not create a
    provider client.
    """

    try:
        from ..env_utils import env_get
    except Exception:

        def env_get(*_args: Any, **_kwargs: Any) -> str:
            return ""

    provider_name = (provider or env_get("UAGENT_PROVIDER") or "").strip().lower()
    if depname is None:
        try:
            from ..llmcapa_util import current_model

            depname = current_model(provider_name)
        except Exception:
            depname = ""
    model_name = (depname or "").strip()

    if use_responses_api is None:
        raw_responses = (env_get("UAGENT_RESPONSES") or "").strip().lower()
        if raw_responses in {"1", "true", "yes", "on"}:
            from .capability_resolver import responses_api_explicit_enabled

            use_responses_api = responses_api_explicit_enabled(
                provider_name,
                model_name,
                resolver=capability_resolver,
            )
        elif raw_responses in {"0", "false", "no", "off"}:
            use_responses_api = False
        else:
            from .capability_resolver import responses_api_auto_enabled

            use_responses_api = responses_api_auto_enabled(
                provider_name,
                model_name,
                resolver=capability_resolver,
            )

    return resolve_tool_discovery(
        provider=provider_name,
        depname=model_name,
        use_responses_api=bool(use_responses_api),
        configured_mode=get_tool_search_mode(provider=provider_name),
        capability_resolver=capability_resolver,
    )


def messages_tool_search_enabled_from_environment() -> bool:
    """Return whether the selected Messages route has native/client deferral."""
    try:
        from ..env_utils import env_get
        from ..llmcapa_util import current_model

        provider = (env_get("UAGENT_PROVIDER") or "").strip().lower()
        if not provider_messages_api_enabled(provider):
            return False
        model = current_model(provider) if provider else ""
        if provider == "deepseek":
            return deepseek_messages_tool_search_enabled(provider, model)
        return anthropic_messages_tool_search_variant(provider, model) is not None
    except Exception:
        return False


def select_tool_specs_for_discovery(
    decision: ToolDiscoveryDecision,
    *,
    legacy_specs: list[dict[str, Any]] | None,
    native_specs: list[dict[str, Any]] | None,
    selected_specs: Any,
) -> Any:
    """Select the already-built provider surface for one discovery decision."""

    if decision.uses_legacy_catalog:
        return legacy_specs
    if decision.uses_native_search:
        return native_specs
    return selected_specs


def resolve_tool_discovery(
    *,
    provider: str,
    depname: str,
    use_responses_api: bool,
    configured_mode: str | None = None,
    capability_resolver: CapabilityResolverPort | None = None,
) -> ToolDiscoveryDecision:
    """Resolve native search, legacy catalog, or selected schemas once.

    Native search is fail-closed and requires a Responses route plus positive
    llmcapa ``tool_search`` evidence for the selected provider/model.
    """

    mode = (configured_mode or "native").strip().lower()
    if mode in {"off", "0", "false", "no"}:
        return ToolDiscoveryDecision(ToolDiscoveryMode.SELECTED_SCHEMAS, "disabled")
    if not use_responses_api:
        return ToolDiscoveryDecision(
            ToolDiscoveryMode.SELECTED_SCHEMAS, "responses_api_disabled"
        )
    provider_name = (provider or "").strip().lower()
    if (
        provider_name == "openrouter"
        and mode == "native"
        and openrouter_responses_tool_search_variant(
            provider_name, depname, configured_mode=mode
        )
        is None
    ):
        return ToolDiscoveryDecision(
            ToolDiscoveryMode.SELECTED_SCHEMAS, "tool_search_unavailable"
        )
    if mode in {"legacy", "old"} and provider_name in {"openrouter", "deepseek"}:
        return ToolDiscoveryDecision(ToolDiscoveryMode.LEGACY_CATALOG, "legacy_mode")
    if provider_name == "deepseek":
        if not deepseek_responses_tool_search_enabled(
            provider_name, depname, configured_mode=mode
        ):
            return ToolDiscoveryDecision(
                ToolDiscoveryMode.SELECTED_SCHEMAS, "tool_search_unavailable"
            )
    try:
        if capability_resolver is None:
            from .capability_resolver import CapabilityResolver

            capability_resolver = CapabilityResolver()
        snapshot = capability_resolver.resolve(
            provider_name, depname, transport="responses"
        )
        tool_search = getattr(snapshot, "tool_search", None)
    except Exception:
        tool_search = None
    if tool_search is None or not tool_search.is_native_allowed():
        return ToolDiscoveryDecision(
            ToolDiscoveryMode.SELECTED_SCHEMAS, "tool_search_unavailable"
        )
    if mode in {"legacy", "old"}:
        return ToolDiscoveryDecision(ToolDiscoveryMode.LEGACY_CATALOG, "legacy_mode")
    return ToolDiscoveryDecision(ToolDiscoveryMode.NATIVE_SEARCH, "native_mode")


@dataclass(frozen=True)
class ToolCandidate:
    """One discoverable tool, without granting it execution permission."""

    name: str
    description: str
    source: ToolSource
    schema: Mapping[str, Any]
    loaded: bool = False
    executable: bool = True
    permission_scope: str = "default"
    delivery_hint: str | None = None


class CapabilityCatalog(Protocol):
    """Read-only source of candidates; it must not load or execute tools."""

    def discover(self, query: str = "") -> tuple[ToolCandidate, ...]: ...


@dataclass(frozen=True)
class ToolSelection:
    """Policy result. Delivery and execution remain separate decisions."""

    selected: tuple[ToolCandidate, ...]
    used_fallback: bool = False


class ToolSelectionPolicy:
    """Select candidates deterministically while preserving management tools."""

    def __init__(self, management_names: Iterable[str] = ()) -> None:
        self._management_names = frozenset(management_names)

    def select(
        self, candidates: Iterable[ToolCandidate], names: Iterable[str] | None = None
    ) -> ToolSelection:
        candidates_tuple = tuple(candidates)
        requested = None if names is None else frozenset(name for name in names if name)
        selected = tuple(
            candidate
            for candidate in candidates_tuple
            if candidate.executable
            and (
                candidate.name in self._management_names
                or requested is None
                or candidate.name in requested
            )
        )
        # A zero-hit query intentionally fails open for the legacy catalog path.
        if requested and not any(item.name in requested for item in selected):
            return ToolSelection(
                tuple(item for item in candidates_tuple if item.executable),
                used_fallback=True,
            )
        return ToolSelection(selected)


@dataclass(frozen=True)
class ToolDelivery:
    mode: ToolDeliveryMode
    tool_specs: tuple[Mapping[str, Any], ...]
    selected_names: tuple[str, ...]


class ToolDeliveryStrategy:
    """Turn an approved selection into provider input, never tool execution."""

    def deliver(
        self,
        selection: ToolSelection,
        *,
        native_search: bool = False,
    ) -> ToolDelivery:
        candidates = selection.selected
        if native_search:
            return ToolDelivery(
                mode=ToolDeliveryMode.PROVIDER_NATIVE_SEARCH,
                tool_specs=tuple(item.schema for item in candidates),
                selected_names=tuple(item.name for item in candidates),
            )
        mode = (
            ToolDeliveryMode.MANAGEMENT_TOOLS
            if all(item.name in MANAGEMENT_TOOL_NAMES for item in candidates)
            else ToolDeliveryMode.LOADED_SPECS
        )
        return ToolDelivery(
            mode=mode,
            tool_specs=tuple(item.schema for item in candidates),
            selected_names=tuple(item.name for item in candidates),
        )


def tool_discovery_debug_enabled() -> bool:
    """True when the opt-in tool-discovery diagnostic is enabled.

    Set UAGENT_DEBUG_TOOL_DISCOVERY=1 to record each round's
    discovery decision (see record_tool_discovery_debug). Off by
    default; the round path pays only this env check.
    """
    try:
        from ..env_utils import env_get

        raw = env_get("UAGENT_DEBUG_TOOL_DISCOVERY")
    except Exception:
        return False
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _tool_discovery_debug_path() -> Any:
    from ..utils.paths import get_log_dir

    return get_log_dir() / "tool_discovery.jsonl"


def record_tool_discovery_debug(
    decision: ToolDiscoveryDecision,
    *,
    provider: str = "",
    depname: str = "",
    use_responses_api: bool = False,
    tool_names: Iterable[str] = (),
    where: str = "",
    session_id: str = "",
) -> None:
    """Append one JSON line describing a round's discovery decision.

    Opt-in only (UAGENT_DEBUG_TOOL_DISCOVERY=1); a no-op otherwise.
    The record carries the decision mode and reason plus whether
    tool_catalog was among the sent tools, so a round where the
    model called tool_catalog unexpectedly can be checked after
    the fact: native rounds never send it, other modes may.
    """
    if not tool_discovery_debug_enabled():
        return
    try:
        import json
        import time

        names = list(tool_names)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session_id": session_id,
            "where": where,
            "provider": provider,
            "model": depname,
            "use_responses_api": bool(use_responses_api),
            "mode": decision.mode.value,
            "reason": decision.reason,
            "tool_count": len(names),
            "catalog_sent": "tool_catalog" in names,
        }
        path = _tool_discovery_debug_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
