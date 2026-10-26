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


def _returned_scope_violations(
    result: MemoryShadowResult,
    records: Sequence[Any],
    *,
    scope: str,
    owner: str,
    project: str,
    strict_scope: bool,
    authorized_memory_revisions: Mapping[str, Any] | None = None,
) -> int:
    """Independently verify returned candidate provenance against fixture records."""
    source_index_by_id = {
        diagnostic.item_id: diagnostic.index for diagnostic in result.diagnostics
    }
    violations = 0
    for candidate in result.candidates:
        source_index = source_index_by_id.get(candidate.item_id)
        if (
            source_index is None
            or source_index < 0
            or source_index >= len(records)
            or not isinstance(records[source_index], Mapping)
        ):
            violations += 1
            continue
        record = records[source_index]
        if authorized_memory_revisions is not None:
            memory_id = str(record.get("memory_id") or "")
            authorized_revision = authorized_memory_revisions.get(memory_id)
            if authorized_revision is None or str(record.get("revision")) != str(
                authorized_revision
            ):
                violations += 1
                continue
        record_scope = str(record.get("scope") or "").strip()
        record_owner = next(
            (
                str(record.get(key) or "").strip()
                for key in ("owner", "owner_id", "user", "user_id")
                if str(record.get(key) or "").strip()
            ),
            "",
        )
        record_project = next(
            (
                str(record.get(key) or "").strip()
                for key in ("project", "project_id")
                if str(record.get(key) or "").strip()
            ),
            "",
        )
        if (
            (record_scope and record_scope.casefold() != scope.casefold())
            or (owner and record_owner and record_owner.casefold() != owner.casefold())
            or (
                project
                and record_project
                and record_project.casefold() != project.casefold()
            )
            or (strict_scope and (not record_owner or not record_project))
            or " ".join(str(record.get("note") or "").split()).casefold()
            != " ".join(str(candidate.content or "").split()).casefold()
        ):
            violations += 1
    return violations


def evaluate_retrieval_case(case: Mapping[str, Any]) -> MemoryEvaluationResult:
    """Evaluate one case without LLM calls, persistence, or model judging."""
    case_id = str(case.get("id") or "case")
    expected = {
        str(note).strip()
        for note in (case.get("expected_notes") or [])
        if str(note).strip()
    }
    strict_scope = bool(case.get("strict_scope", False))
    records = case.get("records") or ()
    result = shadow_retrieve_memories(
        records,
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
    scope_violations = _returned_scope_violations(
        result,
        records,
        scope=str(case.get("scope") or "personal"),
        owner=str(case.get("owner") or ""),
        project=str(case.get("project") or ""),
        strict_scope=strict_scope,
        authorized_memory_revisions=(
            case.get("authorized_memory_revisions")
            if isinstance(case.get("authorized_memory_revisions"), Mapping)
            else None
        ),
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
