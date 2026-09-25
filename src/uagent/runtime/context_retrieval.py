"""Deterministic retrieval adapters for persisted context records."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Sequence

from .active_context import ContextCandidate
from .observability.bootstrap import get_observability_backend

_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


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


__all__ = ["retrieve_candidates"]
