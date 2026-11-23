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


def test_tool_definition_selection_reuses_serialized_specs_and_query_tokens(
    monkeypatch,
):
    from uagent.runtime import context_tools

    specs = [
        {
            "type": "function",
            "function": {"name": "read_file", "description": "read a file"},
        },
        {
            "type": "function",
            "function": {"name": "search_files", "description": "search files"},
        },
    ]
    serialized_specs: list[dict] = []
    tokenized_texts: list[str] = []
    original_tool_text = context_tools._tool_text
    original_tokens = context_tools._tokens

    def count_tool_text(spec):
        serialized_specs.append(spec)
        return original_tool_text(spec)

    def count_tokens(text):
        tokenized_texts.append(text)
        return original_tokens(text)

    monkeypatch.setattr(context_tools, "_tool_text", count_tool_text)
    monkeypatch.setattr(context_tools, "_tokens", count_tokens)

    ContextManager().optimize_tool_definitions(specs, task="read a file")

    assert serialized_specs == specs
    # One tokenization for the task and one for each serialized schema.
    assert tokenized_texts == ["read a file", *[original_tool_text(s) for s in specs]]


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
