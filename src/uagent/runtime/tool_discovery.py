"""Provider-neutral boundaries for discovering, selecting, and delivering tools.

Tool origin is metadata, not a delivery decision: MCP/A2A/skills may have
different permission and invocation paths even when their schemas look alike.
Keeping these phases separate prevents the LLM round loop from becoming a tool
catalog again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol


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
            if all(
                item.name in {"tool_catalog", "tool_load", "unload_tool"}
                for item in candidates
            )
            else ToolDeliveryMode.LOADED_SPECS
        )
        return ToolDelivery(
            mode=mode,
            tool_specs=tuple(item.schema for item in candidates),
            selected_names=tuple(item.name for item in candidates),
        )
