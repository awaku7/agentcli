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
