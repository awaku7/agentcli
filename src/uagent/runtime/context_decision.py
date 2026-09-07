"""Deterministic candidate scoring and context decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .active_context import ContextAction, ContextCandidate, ContextDecision
from .context_budget import ContextBudget


@dataclass(frozen=True)
class DecisionPolicy:
    """Thresholds used by :class:`ContextDecisionEngine`."""

    exclude_score: float = 0.25
    compact_score: float = 0.50
    compact_min_chars: int = 64


class ContextDecisionEngine:
    """Score candidates and select a deterministic, budgeted projection."""

    def __init__(self, *, policy: DecisionPolicy | None = None) -> None:
        self.policy = policy or DecisionPolicy()

    @staticmethod
    def score(candidate: ContextCandidate) -> float:
        """Return a normalized score from available importance signals."""
        values = [
            value
            for value in (
                candidate.importance,
                candidate.relevance,
                candidate.recency,
            )
            if value is not None
        ]
        if not values:
            return 0.5
        return max(0.0, min(1.0, sum(values) / len(values)))

    def decide(
        self,
        candidates: Sequence[ContextCandidate],
        *,
        budget: ContextBudget,
    ) -> list[ContextDecision]:
        """Create decisions without mutating or reordering the input sequence."""
        if budget.total_chars < 0:
            raise ValueError("context budget must be non-negative")

        ranked = sorted(
            enumerate(candidates),
            key=lambda pair: (-self.score(pair[1]), pair[1].item_id, pair[0]),
        )
        # Do not let an unlimited budget fall back to the nominal default
        # total. ``None`` means that all candidates may be retained.
        remaining: int | None = None if budget.unlimited else budget.total_chars
        decisions: dict[str, ContextDecision] = {}

        for _, candidate in ranked:
            score = self.score(candidate)
            original_chars = candidate.original_chars
            if original_chars is None:
                original_chars = len(str(candidate.content))
            original_chars = max(0, original_chars)

            if score < self.policy.exclude_score:
                action: ContextAction = "EXCLUDE"
                projected_chars = 0
                reason = "score below exclusion threshold"
            elif remaining is None or original_chars <= remaining:
                action = "KEEP"
                projected_chars = original_chars
                reason = "fits remaining character budget"
            elif score >= self.policy.compact_score and remaining > 0:
                action = "COMPACT"
                projected_chars = min(original_chars, remaining)
                reason = "compacted to fit remaining character budget"
            else:
                action = "EXCLUDE"
                projected_chars = 0
                reason = "insufficient budget for candidate"

            decisions[candidate.item_id] = ContextDecision(
                item_id=candidate.item_id,
                source=candidate.source,
                section=candidate.section,
                action=action,
                reason=reason,
                importance=score,
                original_chars=original_chars,
                projected_chars=projected_chars,
                reference=candidate.reference,
            )
            if action in ("KEEP", "COMPACT") and remaining is not None:
                remaining -= projected_chars

        return [decisions[candidate.item_id] for candidate in candidates]


__all__ = ["ContextDecisionEngine", "DecisionPolicy"]
