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

    @property
    def reserved_chars(self) -> int:
        return (
            self.system_chars
            + self.tool_definition_chars
            + self.agent_state_chars
            + self.history_chars
            + self.tool_result_chars
        )

    def usage(self, **sections: int) -> dict[str, Any]:
        """Return section totals and warning/compaction decisions."""
        normalized = {name: max(0, int(value)) for name, value in sections.items()}
        used = sum(normalized.values())
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
        }

    def select_evictable(
        self, records: list[dict[str, Any]], *, target_chars: int
    ) -> list[dict[str, Any]]:
        """Select low-value, evictable records until under a target budget."""
        if target_chars < 0:
            raise ValueError("target_chars must be non-negative")
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
