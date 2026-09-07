from uagent.runtime.active_context import ContextCandidate
from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.context_manager import ContextManager
from uagent.runtime.context_policy import ContextPolicy


def test_build_active_context_runs_decision_engine_when_decisions_omitted():
    manager = ContextManager(
        policy=ContextPolicy(budget_chars=1000),
    )
    candidates = [
        ContextCandidate(
            item_id="kept",
            source="tool_result",
            section="tool_results",
            content="important",
            relevance=0.9,
        )
    ]

    active = manager.build_active_context(
        task="do the task",
        candidates=candidates,
        budget=ContextBudget(total_chars=1000),
    )

    assert active.sections["tool_results"] == ["important"]
    assert active.decisions[0].action == "KEEP"
