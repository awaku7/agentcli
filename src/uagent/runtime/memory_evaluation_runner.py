"""Compare V2 memory rollout modes with deterministic local fixtures.

The runner intentionally does not call an LLM or mutate a persistent memory
store.  It compares the existing broad startup-memory baseline with shadow
retrieval, opt-in projection, and strict-scope projection, while also probing
forget invalidation against the production runtime helpers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..util_message import build_long_memory_system_message
from .memory_forget import invalidate_memory_runtime
from .memory_projection import (
    MemoryProjectionItem,
    MemoryProjectionSnapshot,
    apply_memory_projection,
)
from .memory_retrieval import shadow_retrieve_memories

EVALUATION_MODES = ("baseline", "shadow", "projection", "strict_scope")
_DEFAULT_FIXTURE = Path("tests/fixtures/memory_evaluation_cases.json")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _note_hash(note: str) -> str:
    return hashlib.sha256(_clean(note).casefold().encode("utf-8")).hexdigest()[:16]


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _record_note(record: Mapping[str, Any]) -> str:
    return _clean(record.get("note"))


def _record_field(record: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = _clean(record.get(name))
        if value:
            return value
    return ""


def _record_boundary_status(
    record: Mapping[str, Any], *, scope: str, owner: str, project: str
) -> str:
    record_scope = _record_field(record, "scope")
    if record_scope and record_scope.casefold() != scope.casefold():
        return "mismatch"

    record_owner = _record_field(record, "owner", "owner_id", "user", "user_id")
    record_project = _record_field(record, "project", "project_id")
    if owner and record_owner and record_owner.casefold() != owner.casefold():
        return "mismatch"
    if project and record_project and record_project.casefold() != project.casefold():
        return "mismatch"
    if not record_owner or not record_project:
        return "legacy_unknown"
    return "scoped"


def _strict_expected_notes(case: Mapping[str, Any]) -> set[str]:
    """Remove legacy-unknown expectations when strict scope intentionally rejects them."""
    expected = {
        _clean(note) for note in (case.get("expected_notes") or []) if _clean(note)
    }
    records = [
        record for record in (case.get("records") or []) if isinstance(record, dict)
    ]
    scope = _clean(case.get("scope")) or "personal"
    owner = _clean(case.get("owner"))
    project = _clean(case.get("project"))
    adjusted: set[str] = set()
    for note in expected:
        matching = [record for record in records if _record_note(record) == note]
        if not matching:
            adjusted.add(note)
            continue
        if any(
            _record_boundary_status(
                record,
                scope=scope,
                owner=owner,
                project=project,
            )
            == "scoped"
            for record in matching
        ):
            adjusted.add(note)
    return adjusted


def _expected_notes(case: Mapping[str, Any], mode: str) -> set[str]:
    if mode == "strict_scope":
        return _strict_expected_notes(case)
    return {_clean(note) for note in (case.get("expected_notes") or []) if _clean(note)}


def _baseline_selected_records(
    records: Sequence[Mapping[str, Any]], returned_notes: Sequence[str]
) -> list[Mapping[str, Any]]:
    """Map rendered broad-memory bullets back to records in formatter order."""
    remaining = list(range(len(records) - 1, -1, -1))
    selected: list[Mapping[str, Any]] = []
    for note in returned_notes:
        for position, index in enumerate(remaining):
            record = records[index]
            if _record_note(record) == _clean(note):
                selected.append(record)
                remaining.pop(position)
                break
    return selected


def _run_baseline_once(case: Mapping[str, Any]) -> dict[str, Any]:
    records = [
        record for record in (case.get("records") or []) if isinstance(record, dict)
    ]
    message = build_long_memory_system_message(records)
    content = str(message.get("content") or "")
    returned_notes = tuple(
        line[2:].strip()
        for line in content.splitlines()
        if line.startswith("- ") and line[2:].strip()
    )
    selected_records = _baseline_selected_records(records, returned_notes)
    scope = _clean(case.get("scope")) or "personal"
    owner = _clean(case.get("owner"))
    project = _clean(case.get("project"))
    statuses = [
        _record_boundary_status(record, scope=scope, owner=owner, project=project)
        for record in selected_records
    ]
    return {
        "returned_notes": returned_notes,
        "candidate_count": len(returned_notes),
        "candidate_chars": sum(len(note) for note in returned_notes),
        "context_chars": len(content),
        "excluded_count": max(0, len(records) - len(selected_records)),
        "budget_dropped_count": max(0, len(records) - len(selected_records)),
        "scope_violation_count": sum(status == "mismatch" for status in statuses),
        "legacy_unknown_selected_count": sum(
            status == "legacy_unknown" for status in statuses
        ),
    }


def _render_projection(
    scope: str,
    candidates: Sequence[Any],
    *,
    projection_chars: int,
) -> tuple[tuple[str, ...], int, int]:
    items = tuple(
        MemoryProjectionItem(
            scope=scope,
            note=_clean(candidate.content),
            reference=str(candidate.reference or candidate.item_id),
        )
        for candidate in candidates
        if _clean(candidate.content)
    )
    snapshot = MemoryProjectionSnapshot(
        profile_content="",
        evidence_items=items,
        diagnostics={
            "memory_budget_chars": projection_chars,
            "guidance_budget_chars": 0,
        },
    )
    lines = set(snapshot.evidence_content.splitlines())
    returned: list[str] = []
    for item in items:
        note = _clean(item.note)
        line = f"- [{item.scope}] {note} (source: {item.reference})"
        if line in lines:
            returned.append(note)
    return tuple(returned), len(snapshot.evidence_content), len(items) - len(returned)


def _run_retrieval_once(
    case: Mapping[str, Any],
    *,
    strict_scope: bool,
    render_projection: bool,
    projection_chars: int,
) -> dict[str, Any]:
    records = [
        record for record in (case.get("records") or []) if isinstance(record, dict)
    ]
    scope = _clean(case.get("scope")) or "personal"
    owner = _clean(case.get("owner"))
    project = _clean(case.get("project"))
    owner_filter = owner if owner else ("<missing-owner>" if strict_scope else "")
    result = shadow_retrieve_memories(
        records,
        query=str(case.get("query") or ""),
        scope=scope,
        owner=owner_filter,
        project=project,
        max_candidates=int(case.get("max_candidates", 20)),
        allow_legacy_unknown=not strict_scope,
    )
    candidate_notes = tuple(
        _clean(candidate.content)
        for candidate in result.candidates
        if _clean(candidate.content)
    )
    context_chars = 0
    budget_dropped_count = 0
    if render_projection:
        returned_notes, context_chars, budget_dropped_count = _render_projection(
            scope,
            result.candidates,
            projection_chars=projection_chars,
        )
    else:
        returned_notes = candidate_notes

    candidate_ids = {candidate.item_id for candidate in result.candidates}
    candidate_diagnostics = [
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.item_id in candidate_ids and diagnostic.action == "candidate"
    ]
    return {
        "returned_notes": returned_notes,
        "candidate_count": len(candidate_notes),
        "candidate_chars": sum(len(note) for note in candidate_notes),
        "context_chars": context_chars,
        "excluded_count": result.excluded_records,
        "budget_dropped_count": budget_dropped_count,
        "scope_violation_count": sum(
            diagnostic.scope_status in {"mismatch", "scope_unknown"}
            for diagnostic in candidate_diagnostics
        ),
        "legacy_unknown_selected_count": sum(
            diagnostic.scope_status == "legacy_unknown"
            for diagnostic in candidate_diagnostics
        ),
    }


def _run_case_once(
    case: Mapping[str, Any], mode: str, *, projection_chars: int
) -> dict[str, Any]:
    if mode == "baseline":
        return _run_baseline_once(case)
    if mode == "shadow":
        return _run_retrieval_once(
            case,
            strict_scope=False,
            render_projection=False,
            projection_chars=projection_chars,
        )
    if mode == "projection":
        return _run_retrieval_once(
            case,
            strict_scope=False,
            render_projection=True,
            projection_chars=projection_chars,
        )
    if mode == "strict_scope":
        return _run_retrieval_once(
            case,
            strict_scope=True,
            render_projection=True,
            projection_chars=projection_chars,
        )
    raise ValueError(f"unknown evaluation mode: {mode}")


@dataclass(frozen=True)
class ModeCaseResult:
    mode: str
    case_id: str
    passed: bool
    expected_count: int
    returned_count: int
    recall: float
    irrelevant_injection_rate: float
    scope_violation_count: int
    legacy_unknown_selected_count: int
    excluded_count: int
    candidate_count: int
    candidate_chars: int
    context_chars: int
    budget_dropped_count: int
    latency_ms_mean: float
    latency_ms_p95: float
    returned_notes: tuple[str, ...]
    failure_reasons: tuple[str, ...]

    def to_dict(self, *, include_notes: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "mode": self.mode,
            "case_id": self.case_id,
            "passed": self.passed,
            "expected_count": self.expected_count,
            "returned_count": self.returned_count,
            "recall": self.recall,
            "irrelevant_injection_rate": self.irrelevant_injection_rate,
            "scope_violation_count": self.scope_violation_count,
            "legacy_unknown_selected_count": self.legacy_unknown_selected_count,
            "excluded_count": self.excluded_count,
            "candidate_count": self.candidate_count,
            "candidate_chars": self.candidate_chars,
            "context_chars": self.context_chars,
            "budget_dropped_count": self.budget_dropped_count,
            "latency_ms_mean": self.latency_ms_mean,
            "latency_ms_p95": self.latency_ms_p95,
            "returned_note_hashes": [_note_hash(note) for note in self.returned_notes],
            "failure_reasons": list(self.failure_reasons),
        }
        if include_notes:
            data["returned_notes"] = list(self.returned_notes)
        return data


def evaluate_mode_case(
    case: Mapping[str, Any],
    mode: str,
    *,
    projection_chars: int = 4_000,
    iterations: int = 25,
) -> ModeCaseResult:
    if mode not in EVALUATION_MODES:
        raise ValueError(f"unknown evaluation mode: {mode}")
    if projection_chars < 1:
        raise ValueError("projection_chars must be positive")
    if iterations < 1:
        raise ValueError("iterations must be positive")

    # Warm once so import/i18n initialization is not counted as retrieval latency.
    outcome = _run_case_once(case, mode, projection_chars=projection_chars)
    timings: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        outcome = _run_case_once(case, mode, projection_chars=projection_chars)
        timings.append((time.perf_counter_ns() - started) / 1_000_000.0)

    expected = _expected_notes(case, mode)
    returned = tuple(str(note) for note in outcome["returned_notes"])
    returned_set = set(returned)
    hits = len(expected & returned_set)
    unexpected = len(returned_set - expected)
    recall = hits / len(expected) if expected else 1.0
    injection = unexpected / len(returned_set) if returned_set else 0.0
    failures: list[str] = []
    if expected - returned_set:
        failures.append("missing_expected_notes")
    if unexpected:
        failures.append("unexpected_notes")
    if int(outcome["scope_violation_count"]) > 0:
        failures.append("scope_violation")
    if mode == "strict_scope" and int(outcome["legacy_unknown_selected_count"]) > 0:
        failures.append("legacy_unknown_selected_in_strict_scope")

    return ModeCaseResult(
        mode=mode,
        case_id=str(case.get("id") or "case"),
        passed=not failures,
        expected_count=len(expected),
        returned_count=len(returned),
        recall=recall,
        irrelevant_injection_rate=injection,
        scope_violation_count=int(outcome["scope_violation_count"]),
        legacy_unknown_selected_count=int(outcome["legacy_unknown_selected_count"]),
        excluded_count=int(outcome["excluded_count"]),
        candidate_count=int(outcome["candidate_count"]),
        candidate_chars=int(outcome["candidate_chars"]),
        context_chars=int(outcome["context_chars"]),
        budget_dropped_count=int(outcome["budget_dropped_count"]),
        latency_ms_mean=statistics.mean(timings),
        latency_ms_p95=_percentile(timings, 0.95),
        returned_notes=returned,
        failure_reasons=tuple(failures),
    )


def _forget_probe(mode: str, *, projection_chars: int) -> dict[str, Any]:
    sentinel = "memory-evaluation-forget-sentinel"
    core = type("MemoryEvaluationCore", (), {})()
    core.memory_generation = 0
    core.responses_state = {
        "previous_response_id": "previous",
        "active_response_id": "active",
        "_stale_rid_occurred": True,
    }
    messages: list[dict[str, Any]] = [{"role": "user", "content": "continue"}]

    if mode in {"baseline", "shadow"}:
        core._uagent_memory_system_contents = {"personal": {sentinel}}
        before = [
            {"role": "system", "content": sentinel},
            {"role": "user", "content": "continue"},
        ]
        invalidate_memory_runtime(core)
        after = apply_memory_projection(before, None, core)
    else:
        item = MemoryProjectionItem(
            scope="personal",
            note=sentinel,
            reference="memory-evaluation://forget",
        )
        snapshot = MemoryProjectionSnapshot(
            profile_content="",
            evidence_items=(item,),
            diagnostics={
                "memory_budget_chars": projection_chars,
                "guidance_budget_chars": 0,
            },
            generation=0,
        )
        before = apply_memory_projection(messages, snapshot, core)
        invalidate_memory_runtime(core)
        after = apply_memory_projection(before, snapshot, core)

    reappeared = any(sentinel in str(message.get("content") or "") for message in after)
    responses_state = getattr(core, "responses_state", {})
    continuation_cleared = not any(
        key in responses_state
        for key in ("previous_response_id", "active_response_id", "_stale_rid_occurred")
    )
    return {
        "forget_reappearance_count": int(reappeared),
        "provider_continuation_cleared": continuation_cleared,
        "passed": not reappeared and continuation_cleared,
    }


def _aggregate_mode(
    results: Sequence[ModeCaseResult],
    forget_probe: Mapping[str, Any],
    *,
    informational: bool,
) -> dict[str, Any]:
    expected_total = sum(result.expected_count for result in results)
    returned_total = sum(result.returned_count for result in results)
    recall = (
        sum(result.recall * result.expected_count for result in results)
        / expected_total
        if expected_total
        else 1.0
    )
    irrelevant = (
        sum(
            result.irrelevant_injection_rate * result.returned_count
            for result in results
        )
        / returned_total
        if returned_total
        else 0.0
    )
    latency_samples = [result.latency_ms_mean for result in results]
    quality_passed = all(result.passed for result in results)
    safety_passed = (
        sum(result.scope_violation_count for result in results) == 0
        and int(forget_probe.get("forget_reappearance_count", 0)) == 0
        and bool(forget_probe.get("provider_continuation_cleared", False))
    )
    gate_passed: bool | None = (
        None if informational else quality_passed and safety_passed
    )
    return {
        "informational": informational,
        "gate_passed": gate_passed,
        "quality_passed": quality_passed,
        "safety_passed": safety_passed,
        "case_count": len(results),
        "recall": recall,
        "irrelevant_injection_rate": irrelevant,
        "scope_violation_count": sum(
            result.scope_violation_count for result in results
        ),
        "legacy_unknown_selected_count": sum(
            result.legacy_unknown_selected_count for result in results
        ),
        "forget_reappearance_count": int(
            forget_probe.get("forget_reappearance_count", 0)
        ),
        "provider_continuation_cleared": bool(
            forget_probe.get("provider_continuation_cleared", False)
        ),
        "avg_candidate_chars": (
            statistics.mean(result.candidate_chars for result in results)
            if results
            else 0.0
        ),
        "avg_context_chars": (
            statistics.mean(result.context_chars for result in results)
            if results
            else 0.0
        ),
        "latency_ms_mean": statistics.mean(latency_samples) if latency_samples else 0.0,
        "latency_ms_p95": _percentile(latency_samples, 0.95),
    }


def run_evaluation(
    cases: Sequence[Mapping[str, Any]],
    *,
    projection_chars: int = 4_000,
    iterations: int = 25,
    gate_mode: str = "strict_scope",
    include_notes: bool = False,
) -> dict[str, Any]:
    if gate_mode not in EVALUATION_MODES or gate_mode == "baseline":
        raise ValueError("gate_mode must be shadow, projection, or strict_scope")

    modes: dict[str, Any] = {}
    internal_results: dict[str, tuple[ModeCaseResult, ...]] = {}
    for mode in EVALUATION_MODES:
        results = tuple(
            evaluate_mode_case(
                case,
                mode,
                projection_chars=projection_chars,
                iterations=iterations,
            )
            for case in cases
        )
        internal_results[mode] = results
        forget_probe = _forget_probe(mode, projection_chars=projection_chars)
        aggregate = _aggregate_mode(
            results,
            forget_probe,
            informational=mode == "baseline",
        )
        aggregate["results"] = [
            result.to_dict(include_notes=include_notes) for result in results
        ]
        modes[mode] = aggregate

    baseline = modes["baseline"]
    deltas: dict[str, Any] = {}
    for mode in EVALUATION_MODES[1:]:
        current = modes[mode]
        deltas[mode] = {
            "recall_delta": current["recall"] - baseline["recall"],
            "irrelevant_injection_rate_delta": (
                current["irrelevant_injection_rate"]
                - baseline["irrelevant_injection_rate"]
            ),
            "avg_context_chars_delta": (
                current["avg_context_chars"] - baseline["avg_context_chars"]
            ),
            "latency_ms_mean_delta": (
                current["latency_ms_mean"] - baseline["latency_ms_mean"]
            ),
        }

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(cases),
        "projection_chars": projection_chars,
        "iterations": iterations,
        "gate_mode": gate_mode,
        "overall_gate_passed": bool(modes[gate_mode]["gate_passed"]),
        "modes": modes,
        "deltas_vs_baseline": deltas,
        "measurement_notes": [
            "No LLM/provider call is made by this runner.",
            "Latency is local retrieval/render CPU time, not end-to-end model latency.",
            "Shadow mode injects zero provider context by design.",
            "Context chars measure memory evidence/baseline memory text only; profile guidance has dedicated tests.",
            "Memory note bodies are omitted from reports unless include_notes is explicitly enabled.",
        ],
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    modes = report.get("modes") or {}
    lines = [
        "# Memory V2 Evaluation Report",
        "",
        f"- Generated: `{report.get('generated_at_utc', '')}`",
        f"- Cases: {report.get('case_count', 0)}",
        f"- Iterations per case: {report.get('iterations', 0)}",
        f"- Projection budget: {report.get('projection_chars', 0)} chars",
        f"- Gate mode: `{report.get('gate_mode', '')}`",
        f"- Overall gate: **{'PASS' if report.get('overall_gate_passed') else 'FAIL'}**",
        "",
        "| Mode | Recall | Irrelevant injection | Scope violations | Legacy unknown selected | Forget reappearance | Avg context chars | Mean latency ms | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for mode in EVALUATION_MODES:
        item = modes.get(mode) or {}
        gate = (
            "INFO"
            if item.get("gate_passed") is None
            else ("PASS" if item.get("gate_passed") else "FAIL")
        )
        lines.append(
            "| {mode} | {recall:.3f} | {irrelevant:.3f} | {scope} | {legacy} | "
            "{forget} | {context:.1f} | {latency:.3f} | {gate} |".format(
                mode=mode,
                recall=float(item.get("recall", 0.0)),
                irrelevant=float(item.get("irrelevant_injection_rate", 0.0)),
                scope=int(item.get("scope_violation_count", 0)),
                legacy=int(item.get("legacy_unknown_selected_count", 0)),
                forget=int(item.get("forget_reappearance_count", 0)),
                context=float(item.get("avg_context_chars", 0.0)),
                latency=float(item.get("latency_ms_mean", 0.0)),
                gate=gate,
            )
        )

    lines.extend(["", "## Case details", ""])
    for mode in EVALUATION_MODES:
        lines.extend(
            [
                f"### {mode}",
                "",
                "| Case | Recall | Irrelevant | Context chars | Latency ms | Result |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for result in (modes.get(mode) or {}).get("results", []):
            lines.append(
                "| {case_id} | {recall:.3f} | {irrelevant:.3f} | {context} | "
                "{latency:.3f} | {status} |".format(
                    case_id=result.get("case_id", "case"),
                    recall=float(result.get("recall", 0.0)),
                    irrelevant=float(result.get("irrelevant_injection_rate", 0.0)),
                    context=int(result.get("context_chars", 0)),
                    latency=float(result.get("latency_ms_mean", 0.0)),
                    status="PASS" if result.get("passed") else "FAIL",
                )
            )
        lines.append("")

    notes = report.get("measurement_notes") or []
    if notes:
        lines.extend(["## Measurement notes", ""])
        lines.extend(f"- {note}" for note in notes)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = payload.get("retrieval_cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("fixture must contain a retrieval_cases list")
    return [case for case in cases if isinstance(case, dict)]


def _write_text(path: str | Path, content: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare UAG Memory V2 baseline/shadow/projection/strict-scope modes."
    )
    parser.add_argument(
        "--fixture",
        default=str(_DEFAULT_FIXTURE),
        help="JSON fixture containing retrieval_cases.",
    )
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--projection-chars", type=int, default=4_000)
    parser.add_argument(
        "--gate-mode",
        choices=("shadow", "projection", "strict_scope"),
        default="strict_scope",
    )
    parser.add_argument("--json-out", default="")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument(
        "--include-notes",
        action="store_true",
        help="Include raw returned memory notes in the JSON report.",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Return exit code 2 when the selected gate mode fails.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cases = load_cases(args.fixture)
    report = run_evaluation(
        cases,
        projection_chars=args.projection_chars,
        iterations=args.iterations,
        gate_mode=args.gate_mode,
        include_notes=args.include_notes,
    )
    markdown = render_markdown(report)
    print(markdown, end="")
    if args.json_out:
        _write_text(
            args.json_out,
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    if args.markdown_out:
        _write_text(args.markdown_out, markdown)
    if args.enforce and not report["overall_gate_passed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EVALUATION_MODES",
    "ModeCaseResult",
    "build_parser",
    "evaluate_mode_case",
    "load_cases",
    "main",
    "render_markdown",
    "run_evaluation",
]
