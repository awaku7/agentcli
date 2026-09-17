from __future__ import annotations

from uagent.runtime.context_manager import ContextManager
from uagent.runtime.context_policy import ContextPolicy
from uagent.runtime.round_contracts import ContextPlan
from uagent.runtime.round_identity import DeterministicTestWorkspaceKeyProvider


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


def test_context_manager_builds_immutable_round_plan() -> None:
    manager = ContextManager(
        policy=ContextPolicy(provider="openai", model="gpt-test"),
    )
    messages = [{"role": "user", "content": "hello"}]
    plan = manager.build_context_plan(
        workspace_id="test-workspace",
        messages=messages,
        tool_specs=[{"type": "function", "function": {"name": "demo"}}],
        decisions=[{"name": "demo", "selected": True}],
        telemetry={"round": 1},
        key_provider=DeterministicTestWorkspaceKeyProvider(),
    )

    assert isinstance(plan, ContextPlan)
    assert plan.messages[0]["content"] == "hello"
    assert plan.tool_specs[0]["function"]["name"] == "demo"
    assert plan.telemetry["round"] == 1
    assert plan.plan_id

    messages[0]["content"] = "changed"
    assert plan.messages[0]["content"] == "hello"

    same_plan = manager.build_context_plan(
        workspace_id="test-workspace",
        messages=[{"role": "user", "content": "hello"}],
        tool_specs=[{"type": "function", "function": {"name": "demo"}}],
        decisions=[{"name": "demo", "selected": True}],
        telemetry={"round": 1},
        key_provider=DeterministicTestWorkspaceKeyProvider(),
    )
    assert plan.plan_id == same_plan.plan_id
