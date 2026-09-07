from __future__ import annotations

from uagent.runtime.context_policy import ContextPolicy


def test_context_policy_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_ENABLED", "0")
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_CHARS", "1234")
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_CHARS_OPENAI", "4321")
    monkeypatch.setenv("UAGENT_AUTO_RETRIEVE_TOOL_RESULTS", "0")
    monkeypatch.setenv("UAGENT_AUTO_INJECT_AGENT_STATE", "0")
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_ROWS", "9")
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_TOKENS", "321")

    policy = ContextPolicy.from_environment(provider="openai", model="gpt-test")

    assert policy.provider == "openai"
    assert policy.model == "gpt-test"
    assert policy.budget_enabled is False
    assert policy.budget_chars == 4321
    assert policy.auto_retrieve is False
    assert policy.auto_state is False
    assert policy.tool_result_max_rows == 9
    assert policy.budget_tokens == 321


def test_context_policy_supports_unlimited_budget(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_MODE", "unlimited")

    policy = ContextPolicy.from_environment()

    assert policy.budget_unlimited is True


def test_context_policy_is_unlimited_by_default(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_CONTEXT_BUDGET_MODE", raising=False)

    policy = ContextPolicy.from_environment()

    assert policy.budget_unlimited is True


def test_context_policy_supports_explicit_bounded_budget(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_MODE", "bounded")

    policy = ContextPolicy.from_environment()

    assert policy.budget_unlimited is False
