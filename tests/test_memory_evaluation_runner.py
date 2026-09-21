from __future__ import annotations

import json
from pathlib import Path


def _fixture_cases() -> list[dict]:
    fixture = Path(__file__).parent / "fixtures" / "memory_evaluation_cases.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["retrieval_cases"]


def test_v2_evaluation_runner_compares_all_rollout_modes() -> None:
    from uagent.runtime.memory_evaluation_runner import run_evaluation

    report = run_evaluation(
        _fixture_cases(),
        iterations=1,
        projection_chars=4_000,
        gate_mode="strict_scope",
    )

    assert tuple(report["modes"]) == (
        "baseline",
        "shadow",
        "projection",
        "strict_scope",
    )
    assert report["overall_gate_passed"] is True

    baseline = report["modes"]["baseline"]
    projection = report["modes"]["projection"]
    strict_scope = report["modes"]["strict_scope"]

    assert baseline["informational"] is True
    assert baseline["gate_passed"] is None
    assert baseline["irrelevant_injection_rate"] > 0.0
    assert baseline["scope_violation_count"] > 0
    assert baseline["avg_context_chars"] > 0

    assert projection["avg_context_chars"] > 0
    assert projection["irrelevant_injection_rate"] < baseline[
        "irrelevant_injection_rate"
    ]

    assert strict_scope["gate_passed"] is True
    assert strict_scope["recall"] == 1.0
    assert strict_scope["irrelevant_injection_rate"] == 0.0
    assert strict_scope["scope_violation_count"] == 0
    assert strict_scope["legacy_unknown_selected_count"] == 0
    assert strict_scope["forget_reappearance_count"] == 0
    assert strict_scope["provider_continuation_cleared"] is True


def test_runner_report_omits_note_bodies_by_default_and_can_include_them() -> None:
    from uagent.runtime.memory_evaluation_runner import run_evaluation

    cases = _fixture_cases()[:1]
    safe_report = run_evaluation(cases, iterations=1)
    safe_result = safe_report["modes"]["strict_scope"]["results"][0]
    assert "returned_notes" not in safe_result
    assert safe_result["returned_note_hashes"]

    verbose_report = run_evaluation(cases, iterations=1, include_notes=True)
    verbose_result = verbose_report["modes"]["strict_scope"]["results"][0]
    assert verbose_result["returned_notes"] == ["database migration rule"]


def test_runner_markdown_contains_summary_without_memory_note_text() -> None:
    from uagent.runtime.memory_evaluation_runner import render_markdown, run_evaluation

    report = run_evaluation(_fixture_cases(), iterations=1)
    markdown = render_markdown(report)

    assert "# Memory V2 Evaluation Report" in markdown
    assert "| strict_scope |" in markdown
    assert "Overall gate: **PASS**" in markdown
    assert "database migration rule" not in markdown


def test_runner_cli_writes_json_and_markdown(tmp_path) -> None:
    from uagent.runtime.memory_evaluation_runner import main

    fixture = Path(__file__).parent / "fixtures" / "memory_evaluation_cases.json"
    json_out = tmp_path / "report.json"
    markdown_out = tmp_path / "report.md"

    rc = main(
        [
            "--fixture",
            str(fixture),
            "--iterations",
            "1",
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
            "--enforce",
        ]
    )

    assert rc == 0
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["overall_gate_passed"] is True
    assert payload["gate_mode"] == "strict_scope"
    assert markdown_out.read_text(encoding="utf-8").startswith(
        "# Memory V2 Evaluation Report"
    )


def test_strict_scope_adjusts_legacy_expectation_instead_of_counting_it_as_loss() -> None:
    from uagent.runtime.memory_evaluation_runner import evaluate_mode_case

    case = next(case for case in _fixture_cases() if case["id"] == "legacy_compatibility")
    result = evaluate_mode_case(case, "strict_scope", iterations=1)

    assert result.expected_count == 0
    assert result.returned_count == 0
    assert result.recall == 1.0
    assert result.passed is True
