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


def get_tool_search_mode(raw: str | None = None) -> str:
    """Normalize the user-facing native tool-search mode setting."""

    if raw is None:
        try:
            from ..env_utils import env_get

            raw = env_get("UAGENT_GPT54_TOOL_SEARCH")
        except Exception:
            raw = None
    value = (raw or "").strip().lower()
    if value in {"legacy", "old"}:
        return "legacy"
    if value in {"off", "0", "false", "no"}:
        return "off"
    return "native"


_PROVIDER_DEPNAME_ENV: dict[str, tuple[str, str]] = {
    "openai": ("UAGENT_OPENAI_DEPNAME", "gpt-5.4-nano"),
    "azure": ("UAGENT_AZURE_DEPNAME", "gpt-5.4-nano"),
}


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
        env_name, default = _PROVIDER_DEPNAME_ENV.get(provider_name, ("", ""))
        depname = (env_get(env_name, default) if env_name else default) or default
    model_name = (depname or "").strip()

    if use_responses_api is None:
        raw_responses = (env_get("UAGENT_RESPONSES") or "").strip().lower()
        if raw_responses in {"1", "true", "yes", "on"}:
            use_responses_api = True
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
        configured_mode=get_tool_search_mode(),
        capability_resolver=capability_resolver,
    )


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
    configured_mode: str = "native",
    capability_resolver: CapabilityResolverPort | None = None,
) -> ToolDiscoveryDecision:
    """Resolve native search, legacy catalog, or selected schemas once.

    Native search is fail-closed and requires positive llmcapa ``tool_search``
    evidence for an OpenAI/Azure Responses API model.
    """

    mode = (configured_mode or "native").strip().lower()
    if mode in {"off", "0", "false", "no"}:
        return ToolDiscoveryDecision(ToolDiscoveryMode.SELECTED_SCHEMAS, "disabled")
    if not use_responses_api:
        return ToolDiscoveryDecision(
            ToolDiscoveryMode.SELECTED_SCHEMAS, "responses_api_disabled"
        )
    provider_name = (provider or "").strip().lower()
    if provider_name not in {"openai", "azure"}:
        return ToolDiscoveryDecision(
            ToolDiscoveryMode.SELECTED_SCHEMAS, "provider_not_supported"
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
