from uagent.runtime.active_context import ContextCandidate
from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.context_decision import ContextDecisionEngine


def test_decision_engine_prioritizes_high_score_and_preserves_input_order():
    candidates = [
        ContextCandidate(
            item_id="low",
            source="history",
            section="history",
            content="x" * 40,
            relevance=0.1,
        ),
        ContextCandidate(
            item_id="high",
            source="result",
            section="tool_results",
            content="y" * 40,
            relevance=0.9,
        ),
    ]

    decisions = ContextDecisionEngine().decide(
        candidates, budget=ContextBudget(total_chars=40)
    )

    assert [decision.item_id for decision in decisions] == ["low", "high"]
    assert decisions[0].action == "EXCLUDE"
    assert decisions[1].action == "KEEP"


def test_decision_engine_keeps_all_candidates_for_unlimited_budget():
    candidates = [
        ContextCandidate("first", "result", "tool_results", "x" * 100_001),
        ContextCandidate("second", "result", "tool_results", "y" * 100_001),
    ]

    decisions = ContextDecisionEngine().decide(
        candidates, budget=ContextBudget.without_limit()
    )

    assert [decision.action for decision in decisions] == ["KEEP", "KEEP"]
    assert [decision.projected_chars for decision in decisions] == [100_001, 100_001]


def test_decision_engine_compacts_when_remaining_budget_is_smaller():
    candidate = ContextCandidate(
        item_id="large",
        source="result",
        section="tool_results",
        content="z" * 100,
        relevance=0.9,
    )

    decision = ContextDecisionEngine().decide(
        [candidate], budget=ContextBudget(total_chars=30)
    )[0]

    assert decision.action == "COMPACT"
    assert decision.projected_chars == 30


def test_decision_engine_normalizes_persisted_importance_labels():
    candidate = ContextCandidate(
        item_id="important",
        source="result",
        section="tool_results",
        content="important result",
        importance="high",  # type: ignore[arg-type]
    )

    assert ContextDecisionEngine.score(candidate) == 0.75


def test_decision_engine_ignores_unknown_signal_values():
    candidate = ContextCandidate(
        item_id="unknown",
        source="result",
        section="tool_results",
        content="result",
        importance="not-a-level",  # type: ignore[arg-type]
    )

    assert ContextDecisionEngine.score(candidate) == 0.5
