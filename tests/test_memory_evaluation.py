from __future__ import annotations

import json
from pathlib import Path


def test_memory_evaluation_fixture_passes_without_llm_or_persistence() -> None:
    from uagent.runtime.memory_evaluation import evaluate_retrieval_cases

    fixture = Path(__file__).parent / "fixtures" / "memory_evaluation_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))["retrieval_cases"]

    report = evaluate_retrieval_cases(cases)

    assert report.passed is True
    assert report.recall == 1.0
    assert report.irrelevant_injection_rate == 0.0
    assert report.to_dict()["scope_violation_count"] == 0


def test_memory_evaluation_reports_missing_and_unexpected_notes() -> None:
    from uagent.runtime.memory_evaluation import evaluate_retrieval_case

    result = evaluate_retrieval_case(
        {
            "id": "negative-case",
            "scope": "personal",
            "owner": "alice",
            "project": "app",
            "query": "database",
            "strict_scope": True,
            "records": [
                {
                    "note": "database rule",
                    "owner": "alice",
                    "project": "app",
                }
            ],
            "expected_notes": ["missing rule"],
        }
    )

    assert result.passed is False
    assert result.recall == 0.0
    assert "missing_expected_notes" in result.failure_reasons
    assert "unexpected_notes" in result.failure_reasons
