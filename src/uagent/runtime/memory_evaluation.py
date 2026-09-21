"""Deterministic evaluation helpers for memory retrieval rollout gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .memory_retrieval import MemoryShadowResult, shadow_retrieve_memories


@dataclass(frozen=True)
class MemoryEvaluationResult:
    """Bounded metrics for one deterministic retrieval scenario."""

    case_id: str
    passed: bool
    expected_count: int
    returned_count: int
    recall: float
    irrelevant_injection_rate: float
    scope_violation_count: int
    excluded_count: int
    returned_notes: tuple[str, ...]
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "expected_count": self.expected_count,
            "returned_count": self.returned_count,
            "recall": self.recall,
            "irrelevant_injection_rate": self.irrelevant_injection_rate,
            "scope_violation_count": self.scope_violation_count,
            "excluded_count": self.excluded_count,
            "returned_notes": list(self.returned_notes),
            "failure_reasons": list(self.failure_reasons),
        }


@dataclass(frozen=True)
class MemoryEvaluationReport:
    """Aggregate result for a deterministic memory evaluation fixture."""

    results: tuple[MemoryEvaluationResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def recall(self) -> float:
        expected = sum(result.expected_count for result in self.results)
        if expected == 0:
            return 1.0
        return (
            sum(result.recall * result.expected_count for result in self.results)
            / expected
        )

    @property
    def irrelevant_injection_rate(self) -> float:
        returned = sum(result.returned_count for result in self.results)
        if returned == 0:
            return 0.0
        injected = sum(
            result.irrelevant_injection_rate * result.returned_count
            for result in self.results
        )
        return injected / returned

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "case_count": len(self.results),
            "recall": self.recall,
            "irrelevant_injection_rate": self.irrelevant_injection_rate,
            "scope_violation_count": sum(
                result.scope_violation_count for result in self.results
            ),
            "results": [result.to_dict() for result in self.results],
        }


def _notes(result: MemoryShadowResult) -> tuple[str, ...]:
    return tuple(
        str(candidate.content).strip()
        for candidate in result.candidates
        if str(candidate.content or "").strip()
    )


def evaluate_retrieval_case(case: Mapping[str, Any]) -> MemoryEvaluationResult:
    """Evaluate one case without LLM calls, persistence, or model judging."""
    case_id = str(case.get("id") or "case")
    expected = {
        str(note).strip()
        for note in (case.get("expected_notes") or [])
        if str(note).strip()
    }
    strict_scope = bool(case.get("strict_scope", False))
    result = shadow_retrieve_memories(
        case.get("records") or (),
        query=str(case.get("query") or ""),
        scope=str(case.get("scope") or "personal"),
        owner=str(case.get("owner") or ""),
        project=str(case.get("project") or ""),
        max_candidates=int(case.get("max_candidates", 20)),
        allow_legacy_unknown=not strict_scope,
    )
    returned = _notes(result)
    returned_set = set(returned)
    hits = len(expected & returned_set)
    unexpected = len(returned_set - expected)
    recall = hits / len(expected) if expected else 1.0
    injection_rate = unexpected / len(returned_set) if returned_set else 0.0
    scope_violations = sum(
        1
        for diagnostic in result.diagnostics
        if diagnostic.action == "candidate"
        and diagnostic.scope_status in {"mismatch", "scope_unknown"}
    )
    failures: list[str] = []
    if expected - returned_set:
        failures.append("missing_expected_notes")
    if unexpected:
        failures.append("unexpected_notes")
    if scope_violations:
        failures.append("scope_violation")
    if strict_scope and any(
        diagnostic.reason == "scope_unknown" and diagnostic.action == "candidate"
        for diagnostic in result.diagnostics
    ):
        failures.append("legacy_unknown_selected_in_strict_scope")
    return MemoryEvaluationResult(
        case_id=case_id,
        passed=not failures,
        expected_count=len(expected),
        returned_count=len(returned),
        recall=recall,
        irrelevant_injection_rate=injection_rate,
        scope_violation_count=scope_violations,
        excluded_count=result.excluded_records,
        returned_notes=returned,
        failure_reasons=tuple(failures),
    )


def evaluate_retrieval_cases(
    cases: Sequence[Mapping[str, Any]],
) -> MemoryEvaluationReport:
    """Evaluate a sequence of deterministic retrieval cases."""
    return MemoryEvaluationReport(
        results=tuple(evaluate_retrieval_case(case) for case in cases)
    )


__all__ = [
    "MemoryEvaluationReport",
    "MemoryEvaluationResult",
    "evaluate_retrieval_case",
    "evaluate_retrieval_cases",
]
