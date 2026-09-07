from __future__ import annotations

from types import SimpleNamespace

from uagent.runtime.context_budget import ContextBudget
from uagent.runtime.context_manager import ContextManager
from uagent.uagent_llm import _apply_context_budget, _record_context_telemetry


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


def test_context_budget_supports_explicit_unlimited_mode(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_CONTEXT_BUDGET_MODE", "unlimited")
    messages = [
        {"role": "user", "content": "request"},
        {"role": "tool", "content": "old result " * 100},
    ]

    assert _apply_context_budget(messages, core=None) is False
    assert messages[1]["content"].startswith("old result")


def test_unlimited_budget_preserves_active_context() -> None:
    manager = ContextManager(budget=ContextBudget.without_limit())
    messages = [{"role": "user", "content": "x" * 100_001}]

    active = manager.build_message_context(messages)

    assert active.messages[0]["content"] == messages[0]["content"]
    assert active.report.active_chars == 100_001


def test_context_manager_accepts_call_budget_for_active_snapshot() -> None:
    manager = ContextManager(budget=ContextBudget(total_chars=1_000))
    messages = [
        {"role": "user", "content": "request"},
        {"role": "tool", "content": "tool output"},
    ]

    active = manager.build_message_context(
        messages,
        budget=ContextBudget(total_chars=10),
    )

    assert active.messages[0]["role"] == "user"
    assert active.messages[1]["role"] == "tool"
    assert active.report.active_chars <= 10
    assert messages[1]["content"] == "tool output"


def test_context_telemetry_records_message_preserving_projection() -> None:
    core = SimpleNamespace()
    messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "question"},
        {"role": "tool", "content": "result"},
    ]

    report = _record_context_telemetry(messages, core, raw_chars=30)

    assert core.context_report is report
    assert report["raw_chars"] == 30
    assert report["active_chars"] == 19
    assert report["saved_chars"] == 11
    assert report["sections"]["tool"] == {"message_count": 1, "active_chars": 6}
