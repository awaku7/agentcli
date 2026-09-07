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


@dataclass(frozen=True)
class ActiveContext:
    """Provider-neutral context before provider-specific projection."""

    sections: dict[str, list[str]]
    report: ContextReport
    decisions: list[ContextDecision]
    messages: list[dict[str, Any]] = field(default_factory=list)


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
        remaining = (
            None
            if active_budget.unlimited
            else active_budget.total_chars - active_chars
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
            raw_tokens=self._token_count_chars(raw_chars),
            active_tokens=self._token_count_chars(active_chars),
            saved_tokens=max(
                0,
                self._token_count_chars(raw_chars)
                - self._token_count_chars(active_chars),
            ),
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
        excess = (
            0
            if active_budget.unlimited
            else max(0, raw_chars - active_budget.total_chars)
        )
        # Optimize conversation history without dropping message metadata. Older
        # non-system messages are the cheapest context to compact; recent turns
        # and system instructions remain readable for as long as possible.
        recent_start = max(0, len(projected) - 2)
        compaction_order = [
            index
            for index, message in enumerate(projected)
            if index < recent_start and str(message.get("role") or "") != "system"
        ]
        compaction_order.extend(
            index
            for index, message in enumerate(projected)
            if index >= recent_start and str(message.get("role") or "") != "system"
        )
        compaction_order.extend(
            index
            for index, message in enumerate(projected)
            if str(message.get("role") or "") == "system"
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

        active_chars = 0
        for message in projected:
            role = str(message.get("role") or "unknown")
            chars = len(str(message.get("content") or ""))
            active_chars += chars
            stats = sections.setdefault(role, {"message_count": 0, "active_chars": 0})
            stats["message_count"] += 1
            stats["active_chars"] += chars
        report = ContextReport(
            raw_chars=raw_chars,
            active_chars=active_chars,
            saved_chars=raw_chars - active_chars,
            raw_tokens=self._token_count_chars(raw_chars),
            active_tokens=self._token_count_chars(active_chars),
            saved_tokens=max(
                0,
                self._token_count_chars(raw_chars)
                - self._token_count_chars(active_chars),
            ),
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
