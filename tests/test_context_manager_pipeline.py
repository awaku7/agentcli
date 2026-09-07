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


def test_disabled_budget_uses_unlimited_context_even_with_configured_limit():
    manager = ContextManager(
        policy=ContextPolicy(budget_enabled=False, budget_chars=10),
    )
    active = manager.build_active_context(
        task="",
        candidates=[
            ContextCandidate(
                item_id="large",
                source="tool_result",
                section="tool_results",
                content="x" * 100,
            )
        ],
    )

    assert manager.budget.unlimited is True
    assert active.sections["tool_results"] == ["x" * 100]


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


def test_build_active_context_from_records_retrieves_more_when_initial_batch_is_empty():
    manager = ContextManager(policy=ContextPolicy(budget_chars=1000))

    active = manager.build_active_context_from_records(
        task="database migration",
        records=[{"result_id": "migration", "summary": "database migration completed"}],
        max_candidates=0,
    )

    assert active.sections["tool_results"] == ["database migration completed"]
    assert active.decisions[0].item_id == "migration"


def test_build_active_context_from_records_is_bounded_when_all_candidates_are_excluded():
    manager = ContextManager(policy=ContextPolicy(budget_chars=1000))
    active = manager.build_active_context_from_records(
        task="unrelated task",
        records=[
            {
                "result_id": "low",
                "summary": "irrelevant",
                "relevance": 0.0,
                "importance": "low",
                "recency": 0.0,
            },
        ],
        max_candidates=1,
        max_retrieval_rounds=2,
    )

    assert active.sections.get("tool_results", []) == []
    assert active.decisions[0].action == "EXCLUDE"


def test_decision_engine_reports_when_additional_retrieval_is_needed():
    manager = ContextManager(policy=ContextPolicy(budget_chars=1000))
    active = manager.build_active_context(
        task="task",
        candidates=[],
        budget=ContextBudget(total_chars=1000),
    )

    assert manager.decision_engine.needs_additional_retrieval(active.decisions)
