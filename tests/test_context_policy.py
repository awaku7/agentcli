from __future__ import annotations

from uagent.runtime.context_policy import ContextPolicy


def test_context_policy_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_ENABLED", "0")
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_CHARS", "1234")
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_CHARS_OPENAI", "4321")
    monkeypatch.setenv("UAGENT_AUTO_RETRIEVE_TOOL_RESULTS", "0")
    monkeypatch.setenv("UAGENT_AUTO_INJECT_AGENT_STATE", "0")
    monkeypatch.setenv("UAGENT_TOOL_RESULT_MAX_ROWS", "9")

    policy = ContextPolicy.from_environment(provider="openai", model="gpt-test")

    assert policy.provider == "openai"
    assert policy.model == "gpt-test"
    assert policy.budget_enabled is False
    assert policy.budget_chars == 4321
    assert policy.auto_retrieve is False
    assert policy.auto_state is False
    assert policy.tool_result_max_rows == 9
