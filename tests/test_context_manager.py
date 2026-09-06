from __future__ import annotations

from uagent.runtime.context_manager import ContextManager
from uagent.runtime.context_policy import ContextPolicy


def test_context_manager_coordinates_policy_budget_and_results() -> None:
    manager = ContextManager(
        policy=ContextPolicy(budget_chars=1000),
    )

    record, projections = manager.process_result(
        {"status": "success"}, tool_name="example"
    )

    assert manager.policy.budget_chars == 1000
    assert manager.budget.total_chars == 1000
    assert record.summary == "success"
    assert projections.ui_remote["status"] == "success"
    assert manager.usage(history=10)["used_chars"] == 10
