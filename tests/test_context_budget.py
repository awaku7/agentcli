from __future__ import annotations

import pytest

from uagent.runtime.context_budget import ContextBudget


def test_usage_reports_warning_compaction_and_emergency_thresholds() -> None:
    budget = ContextBudget(total_chars=100)

    assert budget.usage(history=79)["warning"] is False
    assert budget.usage(history=80)["warning"] is True
    assert budget.usage(history=90)["compact"] is True
    assert budget.usage(history=100)["emergency"] is True


def test_select_evictable_prefers_low_importance_records() -> None:
    budget = ContextBudget()
    records = [
        {
            "result_id": "critical",
            "size_bytes": 60,
            "importance": "critical",
            "evictable": False,
        },
        {
            "result_id": "normal",
            "size_bytes": 30,
            "importance": "normal",
            "evictable": True,
        },
        {"result_id": "low", "size_bytes": 20, "importance": "low", "evictable": True},
    ]

    selected = budget.select_evictable(records, target_chars=60)

    assert [item["result_id"] for item in selected] == ["low", "normal"]


def test_budget_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        ContextBudget(total_chars=-1)

    with pytest.raises(ValueError):
        ContextBudget().select_evictable([], target_chars=-1)
