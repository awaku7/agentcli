"""Metadata-only observability linkage for persisted Context decision batches."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from .bootstrap import get_observability_backend


def record_persisted_decision_batch(decisions: Sequence[Any]) -> None:
    """Correlate one persisted decision batch with the active trace safely."""

    backend = get_observability_backend()
    if not backend.enabled:
        return
    try:
        counts: Counter[str] = Counter()
        for item in decisions:
            if isinstance(item, dict):
                action = str(item.get("action") or "").upper()
            else:
                action = str(getattr(item, "action", "") or "").upper()
            if action in {"KEEP", "COMPACT", "EXCLUDE", "RETRIEVE_MORE"}:
                counts[action] += 1

        trace_ids = backend.current_trace_ids()
        attributes: dict[str, Any] = {
            "uag.context.decision_batch.count": len(decisions),
            "uag.context.decision_batch.keep": counts["KEEP"],
            "uag.context.decision_batch.compact": counts["COMPACT"],
            "uag.context.decision_batch.exclude": counts["EXCLUDE"],
            "uag.context.decision_batch.retrieve_more": counts["RETRIEVE_MORE"],
        }
        if trace_ids.trace_id:
            attributes["uag.trace_id"] = trace_ids.trace_id
        if trace_ids.span_id:
            attributes["uag.span_id"] = trace_ids.span_id
        backend.record_event("uag.context.decision_batch.persisted", attributes)
    except Exception:
        pass


__all__ = ["record_persisted_decision_batch"]
