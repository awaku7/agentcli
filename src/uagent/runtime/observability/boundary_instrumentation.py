"""Best-effort instrumentation for centralized UAG-owned runtime boundaries."""

from __future__ import annotations

from functools import wraps
from typing import Any

from .bootstrap import get_observability_backend
from .decision_log import record_persisted_decision_batch

_INSTALLED = False


def _install_memory_retrieval_boundary() -> None:
    from .. import memory_projection, memory_retrieval

    original = memory_retrieval.shadow_retrieve_memories
    if getattr(original, "_uag_observability_wrapped", False):
        memory_projection.shadow_retrieve_memories = original
        return

    @wraps(original)
    def observed(*args: Any, **kwargs: Any):
        backend = get_observability_backend()
        scope = str(kwargs.get("scope") or "")
        with backend.start_span(
            "retrieval",
            attributes={
                "uag.retrieval.kind": "memory",
                "uag.memory.scope": scope if scope in {"personal", "shared"} else "",
            },
        ) as span:
            result = original(*args, **kwargs)
            try:
                candidate_count = len(result.candidates)
                span.set_attribute("uag.memory.records", result.total_records)
                span.set_attribute("uag.memory.candidates", candidate_count)
                span.set_attribute("uag.memory.eligible", result.eligible_records)
                span.set_attribute("uag.memory.excluded", result.excluded_records)
                span.set_status("ok")
                backend.record_histogram(
                    "uag.memory.records",
                    result.total_records,
                    {"uag.retrieval.kind": "memory"},
                )
                backend.record_histogram(
                    "uag.memory.candidates",
                    candidate_count,
                    {"uag.retrieval.kind": "memory"},
                )
                backend.record_histogram(
                    "uag.retrieval.records",
                    result.total_records,
                    {"uag.retrieval.kind": "memory"},
                )
                backend.record_histogram(
                    "uag.retrieval.candidates",
                    candidate_count,
                    {"uag.retrieval.kind": "memory"},
                )
            except Exception:
                pass
            return result

    observed._uag_observability_wrapped = True  # type: ignore[attr-defined]
    memory_retrieval.shadow_retrieve_memories = observed
    memory_projection.shadow_retrieve_memories = observed


def _install_decision_log_boundary() -> None:
    from ..session_store import SessionStore

    original = SessionStore.record_context_decisions
    if getattr(original, "_uag_observability_wrapped", False):
        return

    @wraps(original)
    def observed(
        self: Any,
        session_id: str,
        decisions: list[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ):
        result = original(self, session_id, decisions, *args, **kwargs)
        try:
            record_persisted_decision_batch(decisions)
        except Exception:
            pass
        return result

    observed._uag_observability_wrapped = True  # type: ignore[attr-defined]
    SessionStore.record_context_decisions = observed


def install_runtime_boundary_instrumentation() -> None:
    """Install UAG-owned boundary wrappers once; failures never affect runtime."""

    global _INSTALLED
    if _INSTALLED:
        return
    try:
        _install_memory_retrieval_boundary()
        _install_decision_log_boundary()
    except Exception:
        return
    _INSTALLED = True


__all__ = ["install_runtime_boundary_instrumentation"]
