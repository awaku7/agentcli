"""Deterministic retrieval adapters for persisted context records."""

from __future__ import annotations

import re
from typing import Any, Sequence

from .active_context import ContextCandidate

_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


def _tokens(value: Any) -> set[str]:
    return {token.casefold() for token in _WORD_RE.findall(str(value or ""))}


def retrieve_candidates(
    records: Sequence[dict[str, Any]],
    *,
    query: str = "",
    max_candidates: int = 20,
) -> list[ContextCandidate]:
    """Rank persisted records by query overlap and return context candidates."""
    if max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")
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
        content = preview or summary
        record_tokens = _tokens(
            " ".join(
                (
                    record.get("tool_name", ""),
                    summary,
                    preview,
                )
            )
        )
        overlap = (
            len(query_tokens & record_tokens) / len(query_tokens)
            if query_tokens
            else 0.5
        )
        importance_score = importance.get(
            str(record.get("importance") or "normal").casefold(), 0.5
        )
        score = (overlap * 0.7) + (importance_score * 0.3)
        candidate = ContextCandidate(
            item_id=str(record.get("result_id") or f"record-{index}"),
            source="tool_result",
            section="tool_results",
            content=content,
            importance=importance_score,
            relevance=overlap,
            recency=0.5,
            original_chars=len(content),
            reference=str(record.get("artifact_ref") or "") or None,
        )
        ranked.append((score, index, candidate))

    ranked.sort(key=lambda item: (-item[0], item[2].item_id, item[1]))
    return [candidate for _, _, candidate in ranked[:max_candidates]]


__all__ = ["retrieve_candidates"]
