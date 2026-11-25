from __future__ import annotations

from uagent.runtime.active_context import ContextDecision
from uagent.runtime.context_plan_builder import build_context_plan
from uagent.runtime.round_identity import DeterministicTestWorkspaceKeyProvider


def test_build_context_plan_serializes_context_decision_objects() -> None:
    decision = ContextDecision(
        item_id="result-1",
        source="tool_result",
        section="tool_results",
        action="KEEP",
        reason="within budget",
        importance=0.8,
        original_chars=20,
        projected_chars=20,
        reference="artifact://result-1",
    )

    plan = build_context_plan(
        workspace_id="test-workspace",
        messages=[{"role": "user", "content": "hello"}],
        decisions=[decision],
        key_provider=DeterministicTestWorkspaceKeyProvider(),
    )

    assert plan.decisions == (
        {
            "item_id": "result-1",
            "source": "tool_result",
            "section": "tool_results",
            "action": "KEEP",
            "reason": "within budget",
            "importance": 0.8,
            "original_chars": 20,
            "projected_chars": 20,
            "reference": "artifact://result-1",
        },
    )
