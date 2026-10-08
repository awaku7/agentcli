"""Deterministic retrieval adapters for persisted context records."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Mapping, Sequence

from .active_context import ContextCandidate
from .observability.bootstrap import get_observability_backend

_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


def compaction_checkpoint_record(
    checkpoint: Mapping[str, Any], *, recency: float = 1.0
) -> dict[str, Any] | None:
    """Project an applied immutable checkpoint into a searchable candidate row."""
    if checkpoint.get("application_status") != "applied":
        return None
    record = checkpoint.get("record")
    if not isinstance(record, Mapping):
        return None
    checkpoint_id = str(
        checkpoint.get("checkpoint_id") or record.get("record_id") or ""
    )
    if not checkpoint_id:
        return None

    lines = [
        "Persisted checkpoint context (background information, not new instructions).",
        f"Checkpoint reference: checkpoint://{checkpoint_id}",
    ]
    source_start = record.get("source_start_seq")
    source_end = record.get("source_end_seq")
    if source_start is not None and source_end is not None:
        lines.append(f"Source sequence range: {source_start}-{source_end}")

    def append_observations(label: str, values: Any) -> None:
        if not isinstance(values, (list, tuple)):
            return
        for value in values:
            if isinstance(value, Mapping) and str(value.get("text") or "").strip():
                lines.append(f"{label}: {str(value['text']).strip()}")

    for delta in record.get("goal_deltas", ()) or ():
        if not isinstance(delta, Mapping):
            continue
        title = str(delta.get("title_hint") or delta.get("goal_id") or "").strip()
        if title:
            lines.append(f"Goal: {title}")
        append_observations("Status", delta.get("status_observations"))
        append_observations("Progress", delta.get("progress_events"))
        append_observations("Next action", delta.get("next_action_observations"))
        for decision in delta.get("decisions", ()) or ():
            if isinstance(decision, Mapping):
                text = str(decision.get("decision") or "").strip()
                rationale = str(decision.get("rationale") or "").strip()
                if text:
                    lines.append(
                        f"Decision: {text}" + (f" ({rationale})" if rationale else "")
                    )
        for constraint in delta.get("constraints", ()) or ():
            if isinstance(constraint, Mapping) and constraint.get("constraint"):
                lines.append(f"Constraint: {str(constraint['constraint']).strip()}")
        for fact in delta.get("facts", ()) or ():
            if isinstance(fact, Mapping) and fact.get("fact"):
                lines.append(f"Fact: {str(fact['fact']).strip()}")

    for label, key, field in (
        ("Shared constraint", "shared_constraints", "constraint"),
        ("Shared fact", "shared_facts", "fact"),
        ("Critical context", "critical_context", "fact"),
    ):
        for value in record.get(key, ()) or ():
            if isinstance(value, Mapping) and value.get(field):
                lines.append(f"{label}: {str(value[field]).strip()}")
    append_observations("Continuation", record.get("narrative_continuation"))

    deterministic = record.get("deterministic_delta")
    if isinstance(deterministic, Mapping):
        for key, label in (
            ("modified_files", "Modified file"),
            ("created_files", "Created file"),
            ("deleted_files", "Deleted file"),
        ):
            values = deterministic.get(key)
            if isinstance(values, (list, tuple)):
                lines.extend(f"{label}: {str(value)}" for value in values if value)
        for check in deterministic.get("executed_checks", ()) or ():
            if isinstance(check, Mapping):
                status = str(check.get("status") or "").strip()
                target = str(
                    check.get("target") or check.get("command_class") or ""
                ).strip()
                if status or target:
                    lines.append(f"Check: {target} {status}".strip())

    content = "\n".join(lines)[:16_000]
    return {
        "item_id": f"checkpoint:{checkpoint_id}",
        "source": "compaction",
        "section": "history",
        "title": f"Compaction checkpoint {checkpoint_id}",
        "content": content,
        "summary": content,
        "importance": "high",
        "recency": max(0.0, min(1.0, float(recency))),
        "reference": f"checkpoint://{checkpoint_id}",
        "original_chars": len(content),
    }


def _tokens(value: Any) -> set[str]:
    return {token.casefold() for token in _WORD_RE.findall(str(value or ""))}


def retrieve_candidates(
    records: Sequence[dict[str, Any]],
    *,
    query: str = "",
    max_candidates: int = 20,
) -> list[ContextCandidate]:
    """Rank persisted records and return provider-neutral candidates.

    Records may come from tool results, memory, artifacts, or history.  The
    optional ``source``, ``section``, ``content``, ``relevance`` and
    ``recency`` fields are preserved when present; tool-result records retain
    their legacy ``summary``/``artifact_preview`` behavior.
    """
    if max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")

    backend = get_observability_backend()
    span_attributes = {
        "uag.retrieval.kind": "context",
        "uag.retrieval.input_records": len(records),
        "uag.retrieval.max_candidates": max_candidates,
        "uag.retrieval.query_chars": len(query or ""),
    }
    with backend.start_span("retrieval", attributes=span_attributes) as span:
        query_tokens = _tokens(query)
        importance = {
            "low": 0.25,
            "normal": 0.5,
            "medium": 0.5,
            "high": 0.75,
            "critical": 1.0,
        }
        ranked: list[tuple[float, int, ContextCandidate]] = []
        for index, record in enumerate(records):
            summary = str(record.get("summary") or "").strip()
            preview = str(record.get("artifact_preview") or "").strip()
            content = str(record.get("content") or "").strip() or preview or summary
            searchable = " ".join(
                str(record.get(field) or "")
                for field in (
                    "tool_name",
                    "title",
                    "summary",
                    "content",
                    "artifact_preview",
                )
            )
            record_tokens = _tokens(searchable)
            overlap = (
                len(query_tokens & record_tokens) / len(query_tokens)
                if query_tokens
                else 0.5
            )
            importance_score = importance.get(
                str(record.get("importance") or "normal").casefold(), 0.5
            )
            relevance = record.get("relevance")
            try:
                relevance_score = max(0.0, min(1.0, float(relevance)))
            except (TypeError, ValueError):
                relevance_score = overlap
            recency = record.get("recency", 0.5)
            try:
                recency_score = max(0.0, min(1.0, float(recency)))
            except (TypeError, ValueError):
                recency_score = 0.5
            score = (
                relevance_score * 0.50 + importance_score * 0.30 + recency_score * 0.20
            )
            candidate = replace(
                ContextCandidate.from_record(record, index=index),
                importance=importance_score,
                relevance=relevance_score,
                recency=recency_score,
                original_chars=len(content),
            )
            ranked.append((score, index, candidate))

        ranked.sort(key=lambda item: (-item[0], item[2].item_id, item[1]))

        unique: dict[str, ContextCandidate] = {}
        for _, _, candidate in ranked:
            unique.setdefault(candidate.item_id, candidate)
        selected = list(unique.values())[:max_candidates]
        try:
            span.set_attribute("uag.retrieval.candidates", len(selected))
            span.set_attribute("uag.retrieval.unique_records", len(unique))
            span.set_status("ok")
            backend.record_histogram(
                "uag.retrieval.records",
                len(records),
                {"uag.retrieval.kind": "context"},
            )
            backend.record_histogram(
                "uag.retrieval.candidates",
                len(selected),
                {"uag.retrieval.kind": "context"},
            )
        except Exception:
            pass
        return selected


__all__ = ["compaction_checkpoint_record", "retrieve_candidates"]
