"""Provider-neutral active-context selection and budgeted projection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from .context_budget import ContextBudget

ContextAction = Literal["KEEP", "COMPACT", "EXCLUDE", "RETRIEVE_MORE"]


@dataclass(frozen=True)
class ContextCandidate:
    """A retrievable item considered for the current LLM call."""

    item_id: str
    source: str
    section: str
    content: Any
    importance: float | None = None
    relevance: float | None = None
    recency: float | None = None
    original_chars: int | None = None
    reference: str | None = None


@dataclass(frozen=True)
class ContextDecision:
    """The decision engine's action for one candidate."""

    item_id: str
    source: str
    section: str
    action: ContextAction
    reason: str
    importance: float | None = None
    original_chars: int | None = None
    projected_chars: int | None = None
    reference: str | None = None


@dataclass(frozen=True)
class ContextReport:
    """Character-based telemetry for one active-context build."""

    raw_chars: int
    active_chars: int
    raw_tokens: int | None
    active_tokens: int | None
    saved_tokens: int | None
    saved_ratio: float | None
    sections: dict[str, dict[str, int | None]]


@dataclass(frozen=True)
class ActiveContext:
    """Provider-neutral context before provider-specific projection."""

    sections: dict[str, list[str]]
    report: ContextReport
    decisions: list[ContextDecision]


def _to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _truncate(value: str, limit: int) -> str:
    if limit < 0:
        return ""
    if len(value) <= limit:
        return value
    if limit <= 32:
        return value[:limit]
    marker = "\n[context compacted]\n"
    return value[: max(0, limit - len(marker))] + marker


class ActiveContextBuilder:
    """Build a deterministic, bounded active context from candidates."""

    def __init__(self, *, budget: ContextBudget | None = None) -> None:
        self.budget = budget or ContextBudget()

    def build_active_context(
        self,
        *,
        task: str,
        candidates: Sequence[ContextCandidate],
        decisions: Sequence[ContextDecision],
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        active_budget = budget or self.budget
        decision_by_id = {decision.item_id: decision for decision in decisions}
        sections: dict[str, list[str]] = {}
        section_stats: dict[str, dict[str, int | None]] = {}
        raw_chars = len(task or "")
        active_chars = len(task or "")
        remaining = active_budget.total_chars - active_chars

        if task:
            sections["task"] = [task]
            section_stats["task"] = {
                "raw_chars": len(task),
                "active_chars": len(task),
            }

        for candidate in candidates:
            text = _to_text(candidate.content)
            raw_size = len(text)
            raw_chars += raw_size
            decision = decision_by_id.get(candidate.item_id)
            action = decision.action if decision else "KEEP"
            if action in ("EXCLUDE", "RETRIEVE_MORE"):
                section_stats.setdefault(
                    candidate.section, {"raw_chars": 0, "active_chars": 0}
                )
                section_stats[candidate.section]["raw_chars"] = (
                    int(section_stats[candidate.section]["raw_chars"] or 0) + raw_size
                )
                continue

            projected = (
                decision.projected_chars
                if decision and decision.projected_chars is not None
                else raw_size
            )
            if action == "COMPACT":
                text = _truncate(text, max(0, projected))
            elif projected < raw_size and decision is not None:
                text = _truncate(text, max(0, projected))

            allowed = max(0, remaining)
            if len(text) > allowed:
                text = _truncate(text, allowed)
            if not text and raw_size:
                section_stats.setdefault(
                    candidate.section, {"raw_chars": 0, "active_chars": 0}
                )
                section_stats[candidate.section]["raw_chars"] = (
                    int(section_stats[candidate.section]["raw_chars"] or 0) + raw_size
                )
                continue

            sections.setdefault(candidate.section, []).append(text)
            remaining -= len(text)
            active_chars += len(text)
            stats = section_stats.setdefault(
                candidate.section, {"raw_chars": 0, "active_chars": 0}
            )
            stats["raw_chars"] = int(stats["raw_chars"] or 0) + raw_size
            stats["active_chars"] = int(stats["active_chars"] or 0) + len(text)

        raw_chars = max(raw_chars, active_chars)
        report = ContextReport(
            raw_chars=raw_chars,
            active_chars=active_chars,
            raw_tokens=None,
            active_tokens=None,
            saved_tokens=None,
            saved_ratio=(raw_chars - active_chars) / raw_chars if raw_chars else 0.0,
            sections=section_stats,
        )
        return ActiveContext(
            sections=sections,
            report=report,
            decisions=list(decisions),
        )


__all__ = [
    "ActiveContext",
    "ActiveContextBuilder",
    "ContextAction",
    "ContextCandidate",
    "ContextDecision",
    "ContextReport",
]
