from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.context_manager import ContextManager
from uagent.runtime.active_context import ActiveContextBuilder, ContextCandidate


def test_tool_definition_selection_keeps_whole_schemas_and_logs_exclusions():
    specs = [
        {
            "type": "function",
            "function": {"name": "weather", "description": "get weather"},
        },
        {
            "type": "function",
            "function": {"name": "database", "description": "query database"},
        },
    ]
    budget = ContextBudget(
        total_chars=130,
        system_chars=0,
        tool_definition_chars=90,
        agent_state_chars=0,
        history_chars=0,
        tool_result_chars=0,
        artifact_chars=0,
        memory_chars=0,
    )

    selection = ContextManager(budget=budget).optimize_tool_definitions(
        specs, task="weather"
    )

    assert [spec["function"]["name"] for spec in selection.specs] == ["weather"]
    assert selection.active_chars <= budget.total_chars
    assert any(decision.action == "EXCLUDE" for decision in selection.decisions)


def test_token_budget_compacts_active_context():
    context = ActiveContextBuilder(
        budget=ContextBudget(total_chars=100_000, total_tokens=5)
    ).build_active_context(
        task="abcd",
        candidates=[ContextCandidate("result", "tool", "tool_results", "x" * 100)],
        decisions=[],
    )

    assert context.report.active_tokens <= 5
    assert context.report.raw_tokens > context.report.active_tokens
