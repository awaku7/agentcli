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


def test_build_active_context_from_records_runs_retrieval_and_decision():
    manager = ContextManager(policy=ContextPolicy(budget_chars=1000))
    active = manager.build_active_context_from_records(
        task="database migration",
        records=[
            {"result_id": "other", "summary": "weather report"},
            {
                "result_id": "migration",
                "summary": "database migration completed",
                "importance": "high",
            },
        ],
        max_candidates=1,
    )

    assert active.sections["tool_results"] == ["database migration completed"]
    assert active.decisions[0].item_id == "migration"
    assert active.decisions[0].action == "KEEP"
