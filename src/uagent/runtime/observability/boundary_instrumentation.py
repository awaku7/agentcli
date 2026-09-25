"""Best-effort instrumentation for centralized UAG-owned runtime boundaries."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from functools import wraps
from typing import Any

from .bootstrap import get_observability_backend
from .decision_log import record_persisted_decision_batch

_INSTALLED = False


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _install_memory_projection_boundary() -> None:
    from .. import memory_projection

    original = memory_projection.prepare_memory_projection
    if getattr(original, "_uag_observability_wrapped", False):
        return

    @wraps(original)
    def observed(messages: Any, core: Any):
        backend = get_observability_backend()
        with backend.start_span(
            "retrieval", attributes={"uag.retrieval.kind": "memory"}
        ) as span:
            snapshot = original(messages, core)
            try:
                if snapshot is None:
                    span.set_attribute("uag.status", "disabled")
                    span.set_status("ok")
                    return None

                diagnostics = snapshot.diagnostics
                personal = diagnostics.get("personal")
                shared = diagnostics.get("shared")
                personal = personal if isinstance(personal, Mapping) else {}
                shared = shared if isinstance(shared, Mapping) else {}
                total_records = _nonnegative_int(personal.get("total_records"))
                total_records += _nonnegative_int(shared.get("total_records"))
                candidate_count = _nonnegative_int(personal.get("candidate_count"))
                candidate_count += _nonnegative_int(shared.get("candidate_count"))
                evidence_count = _nonnegative_int(diagnostics.get("evidence_count"))
                identity_bound = bool(diagnostics.get("identity_bound", False))
                scope_mode = "scoped" if identity_bound else "local"
                status = "error" if diagnostics.get("error") else "ok"

                span.set_attribute("uag.memory.scope_mode", scope_mode)
                span.set_attribute("uag.memory.identity_bound", identity_bound)
                span.set_attribute(
                    "uag.memory.profile_present",
                    bool(diagnostics.get("profile_present", False)),
                )
                span.set_attribute(
                    "uag.memory.guidance_present",
                    bool(diagnostics.get("guidance_present", False)),
                )
                span.set_attribute("uag.memory.records", total_records)
                span.set_attribute("uag.memory.candidates", candidate_count)
                span.set_attribute("uag.memory.evidence", evidence_count)
                span.set_attribute(
                    "uag.memory.guidance_budget_chars",
                    _nonnegative_int(diagnostics.get("guidance_budget_chars")),
                )
                span.set_attribute(
                    "uag.memory.guidance_budget_used_chars",
                    _nonnegative_int(diagnostics.get("guidance_budget_used_chars")),
                )
                span.set_attribute(
                    "uag.memory.budget_chars",
                    _nonnegative_int(diagnostics.get("memory_budget_chars")),
                )
                span.set_attribute(
                    "uag.memory.budget_used_chars",
                    _nonnegative_int(diagnostics.get("memory_budget_used_chars")),
                )
                span.set_attribute("uag.status", status)
                span.set_status("error" if status == "error" else "ok")

                metric_attributes = {
                    "uag.retrieval.kind": "memory",
                    "uag.memory.scope_mode": scope_mode,
                    "uag.memory.identity_bound": identity_bound,
                }
                backend.record_histogram(
                    "uag.memory.records", total_records, metric_attributes
                )
                backend.record_histogram(
                    "uag.memory.candidates", candidate_count, metric_attributes
                )
                backend.record_histogram(
                    "uag.memory.evidence", evidence_count, metric_attributes
                )
                backend.record_histogram(
                    "uag.retrieval.records",
                    total_records,
                    {"uag.retrieval.kind": "memory"},
                )
                backend.record_histogram(
                    "uag.retrieval.candidates",
                    candidate_count,
                    {"uag.retrieval.kind": "memory"},
                )
            except Exception:
                pass
            return snapshot

    observed._uag_observability_wrapped = True  # type: ignore[attr-defined]
    memory_projection.prepare_memory_projection = observed

    llm_module = sys.modules.get("uagent.uagent_llm")
    if llm_module is not None and getattr(
        llm_module, "prepare_memory_projection", None
    ) is original:
        llm_module.prepare_memory_projection = observed


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
        _install_memory_projection_boundary()
        _install_decision_log_boundary()
    except Exception:
        return
    _INSTALLED = True


__all__ = ["install_runtime_boundary_instrumentation"]
