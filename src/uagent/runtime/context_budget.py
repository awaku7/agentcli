"""Context budget accounting and deterministic eviction candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextBudget:
    """Character budgets for the major context projections."""

    total_chars: int = 100_000
    system_chars: int = 20_000
    tool_definition_chars: int = 20_000
    agent_state_chars: int = 10_000
    history_chars: int = 30_000
    tool_result_chars: int = 20_000
    unlimited: bool = False

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
        )
        if any(value < 0 for value in values):
            raise ValueError("context budgets must be non-negative")
        if self.unlimited:
            return
        object.__setattr__(self, "_scaled_sections", False)
        default_sections = (20_000, 20_000, 10_000, 30_000, 20_000)
        sections = (
            self.system_chars,
            self.tool_definition_chars,
            self.agent_state_chars,
            self.history_chars,
            self.tool_result_chars,
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
                ),
                scaled,
            ):
                object.__setattr__(self, name, value)
            object.__setattr__(self, "_scaled_sections", True)
        if self.reserved_chars > self.total_chars:
            raise ValueError("section budgets must not exceed total context budget")

    @property
    def reserved_chars(self) -> int:
        """Return the sum of explicitly allocated section budgets."""
        return (
            self.system_chars
            + self.tool_definition_chars
            + self.agent_state_chars
            + self.history_chars
            + self.tool_result_chars
        )

    @property
    def reserve_chars(self) -> int:
        """Return the unallocated portion of the total budget."""
        return self.total_chars - self.reserved_chars

    def limit_for_section(self, section: str) -> int | None:
        """Return the explicit budget for a context section."""
        if self.unlimited or getattr(self, "_scaled_sections", False):
            return None
        normalized = str(section or "").strip().casefold().replace("-", "_")
        aliases = {
            "system": "system_chars",
            "instructions": "system_chars",
            "tool": "tool_definition_chars",
            "tools": "tool_definition_chars",
            "tool_definition": "tool_definition_chars",
            "tool_definitions": "tool_definition_chars",
            "agent": "agent_state_chars",
            "state": "agent_state_chars",
            "agent_state": "agent_state_chars",
            "history": "history_chars",
            "conversation": "history_chars",
            "result": "tool_result_chars",
            "results": "tool_result_chars",
            "tool_result": "tool_result_chars",
            "tool_results": "tool_result_chars",
        }
        field_name = aliases.get(normalized)
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


__all__ = ["ContextBudget"]
