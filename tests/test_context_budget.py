from __future__ import annotations

import pytest

from uagent.runtime.context_budget import ContextBudget


def test_usage_reports_warning_compaction_and_emergency_thresholds() -> None:
    budget = ContextBudget(total_chars=100)

    assert budget.usage(history=79)["warning"] is False
    assert budget.usage(history=80)["warning"] is True
    assert budget.usage(history=90)["compact"] is True
    assert budget.usage(history=100)["emergency"] is True


def test_context_budget_exposes_unallocated_reserve() -> None:
    budget = ContextBudget(
        total_chars=100,
        system_chars=10,
        tool_definition_chars=10,
        agent_state_chars=10,
        history_chars=20,
        tool_result_chars=10,
    )

    assert budget.reserved_chars == 60
    assert budget.reserve_chars == 40


def test_context_budget_rejects_section_allocations_over_total() -> None:
    with pytest.raises(ValueError, match="must not exceed total"):
        ContextBudget(total_chars=10, history_chars=11)


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


def test_context_budget_supports_artifacts_and_memory_sections() -> None:
    budget = ContextBudget(
        total_chars=100,
        system_chars=10,
        tool_definition_chars=10,
        agent_state_chars=10,
        history_chars=10,
        tool_result_chars=10,
        artifact_chars=10,
        memory_chars=10,
    )

    assert budget.base_section_budget == 70
    assert budget.reserve_chars == 30
    assert budget.limit_for_section("artifact") == 10
    assert budget.limit_for_section("memory") == 10


def test_context_budget_allocates_reserve_by_deficit_then_priority() -> None:
    budget = ContextBudget(
        total_chars=100,
        system_chars=10,
        tool_definition_chars=10,
        agent_state_chars=10,
        history_chars=10,
        tool_result_chars=10,
        artifact_chars=10,
        memory_chars=10,
    )

    allocations = budget.effective_section_allocations({"history": 80, "memory": 75})

    assert allocations["history"] == 40
    assert allocations["memory"] == 10
    assert sum(allocations.values()) <= budget.total_chars
