from uagent.runtime.active_context import ActiveContextBuilder
from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.context_tokens import estimate_tokens


def test_estimate_tokens_is_dependency_free_and_positive() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("日本語") >= 3


def test_context_report_contains_token_telemetry() -> None:
    context = ActiveContextBuilder(
        budget=ContextBudget.without_limit()
    ).build_active_context(
        task="database migration",
        candidates=[],
        decisions=[],
    )

    assert context.report.raw_tokens == context.report.active_tokens
    assert context.report.raw_tokens > 0
    assert context.report.saved_tokens == 0
