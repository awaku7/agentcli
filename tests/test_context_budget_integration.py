from __future__ import annotations

from uagent.uagent_llm import _apply_context_budget


def test_context_budget_evicts_old_tool_results(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_CHARS", "100")
    messages = [
        {"role": "user", "content": "request"},
        {"role": "tool", "content": "old result " * 10},
        {"role": "assistant", "content": "planning"},
        {"role": "tool", "content": "new result"},
    ]

    assert _apply_context_budget(messages, core=None) is True
    assert messages[1]["content"].startswith("[tool result evicted")
    assert messages[3]["content"] == "new result"


def test_context_budget_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_ENABLED", "0")
    messages = [
        {"role": "user", "content": "request"},
        {"role": "tool", "content": "old result " * 100},
    ]

    assert _apply_context_budget(messages, core=None) is False
    assert messages[1]["content"].startswith("old result")
