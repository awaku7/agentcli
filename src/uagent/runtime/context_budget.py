"""Context budget accounting and deterministic eviction candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONTEXT_SECTIONS = (
    "system",
    "tool_definitions",
    "agent_state",
    "history",
    "tool_results",
    "artifacts",
    "memory",
)

SECTION_PRIORITY = (
    "system",
    "agent_state",
    "tool_results",
    "history",
    "artifacts",
    "memory",
    "tool_definitions",
)


def normalize_section(section: str) -> str:
    """Return the canonical name used for section budget accounting."""
    normalized = str(section or "").strip().casefold().replace("-", "_")
    aliases = {
        "system": "system",
        "instructions": "system",
        "tool": "tool_definitions",
        "tools": "tool_definitions",
        "tool_definition": "tool_definitions",
        "tool_definitions": "tool_definitions",
        "agent": "agent_state",
        "state": "agent_state",
        "agent_state": "agent_state",
        "history": "history",
        "conversation": "history",
        "result": "tool_results",
        "results": "tool_results",
        "tool_result": "tool_results",
        "tool_results": "tool_results",
        "artifact": "artifacts",
        "artifacts": "artifacts",
        "memory": "memory",
    }
    return aliases.get(normalized, normalized)


@dataclass(frozen=True)
class ContextBudget:
    """Character budgets for the major context projections."""

    total_chars: int = 100_000
    system_chars: int = 20_000
    tool_definition_chars: int = 20_000
    agent_state_chars: int = 10_000
    history_chars: int = 30_000
    tool_result_chars: int = 20_000
    artifact_chars: int = 0
    memory_chars: int = 0
    unlimited: bool = False
    # Optional token cap. Character budgets remain the compatibility default.
    total_tokens: int | None = None

    @classmethod
    def without_limit(cls) -> "ContextBudget":
        """Return a budget that records usage but never truncates context."""
        return cls(unlimited=True)

    def __post_init__(self) -> None:
        values = (
            self.total_chars,
            self.system_chars,
            self.tool_definition_chars,
            self.agent_state_chars,
            self.history_chars,
            self.tool_result_chars,
            self.artifact_chars,
            self.memory_chars,
        )
        if any(value < 0 for value in values):
            raise ValueError("context budgets must be non-negative")
        if self.total_tokens is not None and self.total_tokens < 0:
            raise ValueError("total token budget must be non-negative")
        if self.unlimited:
            return
        object.__setattr__(self, "_scaled_sections", False)
        default_sections = (20_000, 20_000, 10_000, 30_000, 20_000, 0, 0)
        sections = (
            self.system_chars,
            self.tool_definition_chars,
            self.agent_state_chars,
            self.history_chars,
            self.tool_result_chars,
            self.artifact_chars,
            self.memory_chars,
        )
        if self.total_chars != 100_000 and sections == default_sections:
            scaled = [self.total_chars * value // 100_000 for value in default_sections]
            scaled[-1] += self.total_chars - sum(scaled)
            for name, value in zip(
                (
                    "system_chars",
                    "tool_definition_chars",
                    "agent_state_chars",
                    "history_chars",
                    "tool_result_chars",
                    "artifact_chars",
                    "memory_chars",
                ),
                scaled,
            ):
                object.__setattr__(self, name, value)
            object.__setattr__(self, "_scaled_sections", True)
        if self.reserved_chars > self.total_chars:
            raise ValueError("section budgets must not exceed total context budget")

    @property
    def reserved_chars(self) -> int:
        """Return the base section budget, excluding the reserve."""
        return (
            self.system_chars
            + self.tool_definition_chars
            + self.agent_state_chars
            + self.history_chars
            + self.tool_result_chars
            + self.artifact_chars
            + self.memory_chars
        )

    @property
    def base_section_budget(self) -> int:
        """Alias used by the Context Runtime design documentation."""
        return self.reserved_chars

    @property
    def reserve_chars(self) -> int:
        """Return the unallocated portion of the total budget."""
        return self.total_chars - self.reserved_chars

    def section_allocations(self) -> dict[str, int]:
        """Return the configured base allocation for every known section."""
        return {
            "system": self.system_chars,
            "tool_definitions": self.tool_definition_chars,
            "agent_state": self.agent_state_chars,
            "history": self.history_chars,
            "tool_results": self.tool_result_chars,
            "artifacts": self.artifact_chars,
            "memory": self.memory_chars,
        }

    def effective_section_allocations(
        self, required_by_section: dict[str, int] | None = None
    ) -> dict[str, int]:
        """Allocate reserve to the most deficient sections deterministically."""
        base = self.section_allocations()
        if self.unlimited:
            return {section: 2**63 - 1 for section in CONTEXT_SECTIONS}
        required = {
            normalize_section(section): max(0, int(value))
            for section, value in (required_by_section or {}).items()
        }
        deficits = {
            section: max(0, required.get(section, 0) - allocation)
            for section, allocation in base.items()
        }
        priority = {section: index for index, section in enumerate(SECTION_PRIORITY)}
        order = sorted(
            CONTEXT_SECTIONS,
            key=lambda section: (-deficits[section], priority[section]),
        )
        remaining = self.reserve_chars
        effective = dict(base)
        for section in order:
            if remaining <= 0:
                break
            allocation = min(deficits[section], remaining)
            effective[section] += allocation
            remaining -= allocation
        return effective

    def limit_for_section(self, section: str) -> int | None:
        """Return the explicit budget for a context section."""
        if self.unlimited or getattr(self, "_scaled_sections", False):
            return None
        field_name = {
            "system": "system_chars",
            "tool_definitions": "tool_definition_chars",
            "agent_state": "agent_state_chars",
            "history": "history_chars",
            "tool_results": "tool_result_chars",
            "artifacts": "artifact_chars",
            "memory": "memory_chars",
        }.get(normalize_section(section))
        return getattr(self, field_name) if field_name else None

    def usage(self, **sections: int) -> dict[str, Any]:
        """Return section totals and warning/compaction decisions."""
        normalized = {name: max(0, int(value)) for name, value in sections.items()}
        used = sum(normalized.values())
        if self.unlimited:
            return {
                "sections": normalized,
                "used_chars": used,
                "total_chars": None,
                "remaining_chars": None,
                "ratio": 0.0,
                "warning": False,
                "compact": False,
                "emergency": False,
                "unlimited": True,
            }
        threshold = max(1, self.total_chars)
        ratio = used / threshold
        return {
            "sections": normalized,
            "used_chars": used,
            "total_chars": self.total_chars,
            "remaining_chars": max(0, self.total_chars - used),
            "ratio": ratio,
            "warning": ratio >= 0.80,
            "compact": ratio >= 0.90,
            "emergency": ratio >= 1.0,
            "unlimited": False,
        }

    def select_evictable(
        self, records: list[dict[str, Any]], *, target_chars: int
    ) -> list[dict[str, Any]]:
        """Select low-value, evictable records until under a target budget."""
        if target_chars < 0:
            raise ValueError("target_chars must be non-negative")
        if self.unlimited:
            return []
        total = sum(max(0, int(item.get("size_bytes") or 0)) for item in records)
        if total <= target_chars:
            return []
        importance_rank = {"low": 0, "normal": 1, "high": 2, "critical": 3}
        candidates = [item for item in records if bool(item.get("evictable", True))]
        candidates.sort(
            key=lambda item: (
                importance_rank.get(str(item.get("importance") or "normal"), 1),
                str(item.get("created_at") or ""),
            )
        )
        selected: list[dict[str, Any]] = []
        for item in candidates:
            selected.append(item)
            total -= max(0, int(item.get("size_bytes") or 0))
            if total <= target_chars:
                break
        return selected


__all__ = [
    "CONTEXT_SECTIONS",
    "SECTION_PRIORITY",
    "ContextBudget",
    "normalize_section",
]
