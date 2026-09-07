"""Deterministic candidate scoring and context decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .active_context import ContextAction, ContextCandidate, ContextDecision
from .context_budget import ContextBudget, normalize_section


@dataclass(frozen=True)
class DecisionPolicy:
    """Thresholds and signal weights used by the decision engine."""

    exclude_score: float = 0.25
    compact_score: float = 0.50
    compact_min_chars: int = 64
    # Relevance is the strongest signal for task-specific context.  Weights
    # are renormalized over signals that are actually present on a candidate.
    relevance_weight: float = 0.50
    importance_weight: float = 0.30
    recency_weight: float = 0.20


class ContextDecisionEngine:
    """Score candidates and select a deterministic, budgeted projection."""

    def __init__(self, *, policy: DecisionPolicy | None = None) -> None:
        self.policy = policy or DecisionPolicy()

    @staticmethod
    def score(
        candidate: ContextCandidate,
        *,
        policy: DecisionPolicy | None = None,
    ) -> float:
        """Return a weighted, normalized score from available signals.

        Missing signals do not dilute a candidate's score: configured weights
        are renormalized over values that can actually be evaluated.  This
        keeps legacy records (which often contain only ``importance``) useful
        while allowing task relevance and recency to guide newer records.
        """
        active_policy = policy or DecisionPolicy()
        signals = (
            (candidate.relevance, active_policy.relevance_weight),
            (candidate.importance, active_policy.importance_weight),
            (candidate.recency, active_policy.recency_weight),
        )
        weighted = [
            (normalized, weight)
            for value, weight in signals
            if weight > 0
            and (normalized := ContextDecisionEngine._normalize_signal(value))
            is not None
        ]
        if not weighted:
            return 0.5
        weight_total = sum(weight for _, weight in weighted)
        return max(
            0.0,
            min(1.0, sum(value * weight for value, weight in weighted) / weight_total),
        )

    @staticmethod
    def _normalize_signal(value: Any) -> float | None:
        """Normalize numeric and persisted importance labels to ``0..1``."""
        if value is None:
            return None
        if isinstance(value, str):
            label = value.strip().casefold()
            labels = {
                "low": 0.25,
                "normal": 0.5,
                "medium": 0.5,
                "high": 0.75,
                "critical": 1.0,
            }
            if label in labels:
                return labels[label]
            try:
                value = float(label)
            except ValueError:
                return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

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
            key=lambda pair: (
                -self.score(pair[1], policy=self.policy),
                pair[1].item_id,
                pair[0],
            ),
        )
        # Do not let an unlimited budget fall back to the nominal default
        # total. ``None`` means that all candidates may be retained.
        remaining: int | None = None if budget.unlimited else budget.total_chars
        section_remaining: dict[str, int] = {}
        if not budget.unlimited and not getattr(budget, "_scaled_sections", False):
            required: dict[str, int] = {}
            for candidate in candidates:
                section = normalize_section(candidate.section)
                if section not in budget.section_allocations():
                    continue
                original = candidate.original_chars
                if original is None:
                    original = len(str(candidate.content))
                if (
                    self.score(candidate, policy=self.policy)
                    >= self.policy.exclude_score
                ):
                    required[section] = required.get(section, 0) + max(0, original)
            section_remaining = budget.effective_section_allocations(required)
        decisions: dict[str, ContextDecision] = {}

        for _, candidate in ranked:
            score = self.score(candidate, policy=self.policy)
            original_chars = candidate.original_chars
            if original_chars is None:
                original_chars = len(str(candidate.content))
            original_chars = max(0, original_chars)

            if score < self.policy.exclude_score:
                action: ContextAction = "EXCLUDE"
                projected_chars = 0
                reason = "score below exclusion threshold"
            else:
                section_name = normalize_section(candidate.section)
                section_left = section_remaining.get(section_name)
                available = remaining
                if available is not None and section_left is not None:
                    available = min(available, section_left)
                if available is None or original_chars <= available:
                    action = "KEEP"
                    projected_chars = original_chars
                    reason = "fits remaining character budget"
                elif score >= self.policy.compact_score and available > 0:
                    action = "COMPACT"
                    projected_chars = min(original_chars, available)
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
                if section_left is not None:
                    section_used = min(projected_chars, section_left)
                    section_remaining[section_name] = section_left - section_used

        return [decisions[candidate.item_id] for candidate in candidates]

    @staticmethod
    def needs_additional_retrieval(
        decisions: Sequence[ContextDecision],
    ) -> bool:
        """Return whether the current candidates yielded usable context.

        Additional retrieval is only appropriate when every candidate was
        excluded (or when no candidates were returned). Keeping this rule in
        the decision layer prevents the retrieval loop from bypassing scoring
        and projection decisions.
        """
        return not any(decision.action in ("KEEP", "COMPACT") for decision in decisions)


__all__ = ["ContextDecisionEngine", "DecisionPolicy"]
