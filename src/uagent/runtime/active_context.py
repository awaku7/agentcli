"""Provider-neutral active-context selection and budgeted projection."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from .context_budget import ContextBudget
from .context_tokens import estimate_tokens

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

    @classmethod
    def from_record(
        cls,
        record: dict[str, Any],
        *,
        index: int = 0,
        default_section: str = "tool_results",
    ) -> "ContextCandidate":
        """Create a provider-neutral candidate from a persisted record."""
        content = record.get("content")
        if content in (None, ""):
            content = record.get("artifact_preview") or record.get("summary") or ""
        return cls(
            item_id=str(
                record.get("result_id") or record.get("item_id") or f"record-{index}"
            ),
            source=str(record.get("source") or "tool_result"),
            section=str(record.get("section") or default_section),
            content=content,
            importance=record.get("importance"),
            relevance=record.get("relevance"),
            recency=record.get("recency"),
            original_chars=record.get("original_chars"),
            reference=str(record.get("artifact_ref") or record.get("reference") or "")
            or None,
        )


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

    def to_dict(self) -> dict[str, Any]:
        """Return a stable, serializable decision-log entry."""
        return {
            "item_id": self.item_id,
            "source": self.source,
            "section": self.section,
            "action": self.action,
            "reason": self.reason,
            "importance": self.importance,
            "original_chars": self.original_chars,
            "projected_chars": self.projected_chars,
            "reference": self.reference,
        }


@dataclass(frozen=True)
class ContextReport:
    """Character-based telemetry for one active-context build."""

    raw_chars: int
    active_chars: int
    saved_chars: int
    raw_tokens: int | None
    active_tokens: int | None
    saved_tokens: int | None
    saved_ratio: float | None
    sections: dict[str, dict[str, int | None]]

    def to_dict(self) -> dict[str, Any]:
        """Return telemetry in a JSON-serializable form."""
        return {
            "raw_chars": self.raw_chars,
            "active_chars": self.active_chars,
            "saved_chars": self.saved_chars,
            "raw_tokens": self.raw_tokens,
            "active_tokens": self.active_tokens,
            "saved_tokens": self.saved_tokens,
            "saved_ratio": self.saved_ratio,
            "sections": copy.deepcopy(self.sections),
        }


@dataclass(frozen=True)
class ActiveContext:
    """Provider-neutral context before provider-specific projection."""

    sections: dict[str, list[str]]
    report: ContextReport
    decisions: list[ContextDecision]
    messages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def decision_log(self) -> list[dict[str, Any]]:
        """Return the per-candidate decision log for diagnostics/export."""
        return [decision.to_dict() for decision in self.decisions]

    def debug_snapshot(self) -> dict[str, Any]:
        """Return the raw/active comparison used by debug UIs and logs."""
        telemetry = self.report.to_dict()
        return {
            "raw_context": {
                "chars": self.report.raw_chars,
                "tokens": self.report.raw_tokens,
            },
            "active_context": {
                "chars": self.report.active_chars,
                "tokens": self.report.active_tokens,
            },
            "saved_chars": self.report.saved_chars,
            "saved_tokens": self.report.saved_tokens,
            "saved_ratio": self.report.saved_ratio,
            "sections": telemetry["sections"],
            "decision_log": self.decision_log,
        }


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


def _truncate_to_tokens(value: str, limit: int, token_counter: Any) -> str:
    """Return the longest deterministic prefix within a token budget."""
    if limit <= 0:
        return ""
    if token_counter(value) <= limit:
        return value
    low, high = 0, len(value)
    best = ""
    while low <= high:
        midpoint = (low + high) // 2
        candidate = value[:midpoint]
        if token_counter(candidate) <= limit:
            best = candidate
            low = midpoint + 1
        else:
            high = midpoint - 1
    return best


def _history_priority(
    message: dict[str, Any], index: int, total: int
) -> tuple[int, int, int]:
    """Return a deterministic eviction priority for one history message.

    Lower values are compacted first. Recent turns and task-significant
    messages therefore survive longer than old tool output, while system
    instructions remain the final fallback for compaction.
    """
    role = str(message.get("role") or "")
    content = str(message.get("content") or "").casefold()
    recent = 1 if index >= max(0, total - 2) else 0
    if role == "system":
        importance = 3
    elif role == "tool":
        importance = 0
    elif any(
        marker in content
        for marker in (
            "requirement",
            "constraint",
            "decision",
            "dependency",
            "error",
            "current task",
            "known fact",
            "pending",
        )
    ):
        importance = 2
    else:
        importance = 1
    return (1 if role == "system" else 0, recent, importance, index)


class ActiveContextBuilder:
    """Build a deterministic, bounded active context from candidates."""

    def __init__(
        self,
        *,
        budget: ContextBudget | None = None,
        provider: str = "",
        model: str = "",
    ) -> None:
        self.budget = budget or ContextBudget()
        self.provider = provider
        self.model = model

    def _token_count(self, value: Any) -> int:
        return estimate_tokens(value, provider=self.provider, model=self.model)

    def _token_count_chars(self, chars: int) -> int:
        # Character totals are retained for compatibility; use the same
        # dependency-free estimator for telemetry when only totals remain.
        return self._token_count("x" * max(0, chars))

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
        raw_tokens = self._token_count(task)
        active_tokens = raw_tokens
        remaining = (
            None
            if active_budget.unlimited
            else active_budget.total_chars - active_chars
        )
        remaining_tokens = (
            None
            if active_budget.unlimited or active_budget.total_tokens is None
            else active_budget.total_tokens - self._token_count(task)
        )

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
            raw_tokens += self._token_count(text)
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

            allowed = None if remaining is None else max(0, remaining)
            if allowed is not None and len(text) > allowed:
                text = _truncate(text, allowed)
            if remaining_tokens is not None:
                text = _truncate_to_tokens(
                    text, max(0, remaining_tokens), self._token_count
                )
            if not text and raw_size:
                section_stats.setdefault(
                    candidate.section, {"raw_chars": 0, "active_chars": 0}
                )
                section_stats[candidate.section]["raw_chars"] = (
                    int(section_stats[candidate.section]["raw_chars"] or 0) + raw_size
                )
                continue

            sections.setdefault(candidate.section, []).append(text)
            if remaining is not None:
                remaining -= len(text)
            if remaining_tokens is not None:
                remaining_tokens -= self._token_count(text)
            active_tokens += self._token_count(text)
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
            saved_chars=raw_chars - active_chars,
            raw_tokens=raw_tokens,
            active_tokens=active_tokens,
            saved_tokens=max(0, raw_tokens - active_tokens),
            saved_ratio=(raw_chars - active_chars) / raw_chars if raw_chars else 0.0,
            sections=section_stats,
        )
        return ActiveContext(
            sections=sections,
            report=report,
            decisions=list(decisions),
        )

    def build_message_context(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        budget: ContextBudget | None = None,
    ) -> ActiveContext:
        """Capture ordered messages while applying a conservative char budget.

        Message metadata and ordering are preserved. If the budget is
        exceeded, only textual content fields are compacted.
        """
        projected = [
            copy.deepcopy(message) for message in messages if isinstance(message, dict)
        ]
        active_budget = budget or self.budget
        sections: dict[str, dict[str, int]] = {}
        raw_chars = sum(len(str(message.get("content") or "")) for message in projected)
        raw_tokens = sum(
            self._token_count(message.get("content")) for message in projected
        )
        excess = (
            0
            if active_budget.unlimited
            else max(0, raw_chars - active_budget.total_chars)
        )
        # Optimize history by semantic importance, recency, and role rather
        # than FIFO alone. Tool output is cheapest to compact; requirements,
        # decisions, errors, and dependencies survive longer.
        compaction_order = sorted(
            range(len(projected)),
            key=lambda index: _history_priority(
                projected[index], index, len(projected)
            ),
        )
        for index in compaction_order:
            if excess <= 0:
                break
            message = projected[index]
            content = message.get("content")
            if not isinstance(content, str) or not content:
                continue
            reduction = min(len(content), excess)
            message["content"] = _truncate(content, len(content) - reduction)
            excess -= reduction

        if not active_budget.unlimited and active_budget.total_tokens is not None:
            token_remaining = active_budget.total_tokens
            for index in compaction_order:
                message = projected[index]
                content = message.get("content")
                if not isinstance(content, str) or not content:
                    continue
                compacted = _truncate_to_tokens(
                    content, max(0, token_remaining), self._token_count
                )
                message["content"] = compacted
                token_remaining -= self._token_count(compacted)

        active_chars = 0
        active_tokens = 0
        for message in projected:
            role = str(message.get("role") or "unknown")
            chars = len(str(message.get("content") or ""))
            active_chars += chars
            active_tokens += self._token_count(message.get("content"))
            stats = sections.setdefault(role, {"message_count": 0, "active_chars": 0})
            stats["message_count"] += 1
            stats["active_chars"] += chars
        report = ContextReport(
            raw_chars=raw_chars,
            active_chars=active_chars,
            saved_chars=raw_chars - active_chars,
            raw_tokens=raw_tokens,
            active_tokens=active_tokens,
            saved_tokens=max(0, raw_tokens - active_tokens),
            saved_ratio=(raw_chars - active_chars) / raw_chars if raw_chars else 0.0,
            sections=sections,
        )
        return ActiveContext(
            sections={},
            report=report,
            decisions=[],
            messages=projected,
        )


__all__ = [
    "ActiveContext",
    "ActiveContextBuilder",
    "ContextAction",
    "ContextCandidate",
    "ContextDecision",
    "ContextReport",
]
