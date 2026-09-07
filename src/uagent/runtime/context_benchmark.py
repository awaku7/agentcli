"""Offline benchmark harness for comparing raw and active context."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .active_context import ContextCandidate
from .context_budget import ContextBudget
from .context_manager import ContextManager
from .context_tokens import estimate_tokens


@dataclass(frozen=True)
class ContextBenchmarkCase:
    """One deterministic context-runtime benchmark input."""

    case_id: str
    task: str
    candidates: Sequence[ContextCandidate]
    output_tokens: int = 0
    success: bool | None = None


def _case_from_value(
    value: ContextBenchmarkCase | Mapping[str, Any], index: int
) -> ContextBenchmarkCase:
    if isinstance(value, ContextBenchmarkCase):
        return value
    raw_candidates = value.get("candidates") or []
    candidates = [
        (
            candidate
            if isinstance(candidate, ContextCandidate)
            else ContextCandidate.from_record(candidate, index=item_index)
        )
        for item_index, candidate in enumerate(raw_candidates)
        if isinstance(candidate, (ContextCandidate, dict))
    ]
    return ContextBenchmarkCase(
        case_id=str(value.get("case_id") or value.get("id") or f"case-{index}"),
        task=str(value.get("task") or ""),
        candidates=candidates,
        output_tokens=max(0, int(value.get("output_tokens") or 0)),
        success=value.get("success"),
    )


def run_context_benchmark(
    cases: Iterable[ContextBenchmarkCase | Mapping[str, Any]],
    *,
    manager: ContextManager | None = None,
    budget: ContextBudget | None = None,
) -> dict[str, Any]:
    """Compare unfiltered baseline context with the active-context pipeline."""
    context_manager = manager or ContextManager(budget=budget)
    samples: list[dict[str, Any]] = []
    for index, raw_case in enumerate(cases):
        case = _case_from_value(raw_case, index)
        raw_parts = [case.task] + [
            str(candidate.content or "") for candidate in case.candidates
        ]
        raw_chars = sum(len(part) for part in raw_parts)
        raw_tokens = sum(estimate_tokens(part) for part in raw_parts)

        started = time.perf_counter()
        active = context_manager.build_active_context(
            task=case.task,
            candidates=case.candidates,
            budget=budget,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        compaction_count = sum(
            decision.action == "COMPACT" for decision in active.decisions
        )
        samples.append(
            {
                "case_id": case.case_id,
                "baseline": {
                    "raw_chars": raw_chars,
                    "active_chars": raw_chars,
                    "raw_tokens": raw_tokens,
                    "active_tokens": raw_tokens,
                },
                "runtime": {
                    "raw_chars": active.report.raw_chars,
                    "active_chars": active.report.active_chars,
                    "raw_tokens": active.report.raw_tokens,
                    "active_tokens": active.report.active_tokens,
                    "saved_chars": active.report.saved_chars,
                    "saved_ratio": active.report.saved_ratio,
                    "latency_ms": round(elapsed_ms, 3),
                    "tool_calls": sum(
                        candidate.source == "tool_result"
                        for candidate in case.candidates
                    ),
                    "compaction_count": compaction_count,
                },
                "output_tokens": case.output_tokens,
                "success": case.success,
            }
        )

    success_values = [
        sample["success"] for sample in samples if sample["success"] is not None
    ]
    return {
        "sample_count": len(samples),
        "samples": samples,
        "success_rate": (
            sum(bool(value) for value in success_values) / len(success_values)
            if success_values
            else None
        ),
    }


__all__ = ["ContextBenchmarkCase", "run_context_benchmark"]
