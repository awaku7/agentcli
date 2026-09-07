from __future__ import annotations

from uagent.runtime.active_context import (
    ActiveContextBuilder,
    ContextCandidate,
    ContextDecision,
)
from uagent.runtime.context_budget import ContextBudget


def test_active_context_builder_applies_actions_and_budget() -> None:
    candidates = [
        ContextCandidate("keep", "history", "history", "short"),
        ContextCandidate("compact", "tool", "tool_result", {"value": "x" * 50}),
        ContextCandidate("exclude", "memory", "memory", "do not include"),
    ]
    decisions = [
        ContextDecision("keep", "history", "history", "KEEP", "needed"),
        ContextDecision(
            "compact",
            "tool",
            "tool_result",
            "COMPACT",
            "large output",
            projected_chars=12,
        ),
        ContextDecision("exclude", "memory", "memory", "EXCLUDE", "not relevant"),
    ]

    context = ActiveContextBuilder(
        budget=ContextBudget(total_chars=40),
    ).build_active_context(
        task="task",
        candidates=candidates,
        decisions=decisions,
    )

    assert context.sections["task"] == ["task"]
    assert context.sections["history"] == ["short"]
    assert len(context.sections["tool_result"][0]) <= 12
    assert "memory" not in context.sections
    assert context.report.active_chars <= 40
    assert context.report.raw_chars > context.report.active_chars


def test_message_context_preserves_order_and_tool_shape() -> None:
    messages = [
        {"role": "user", "content": "request"},
        {"role": "assistant", "tool_calls": [{"id": "call-1"}]},
        {"role": "tool", "tool_call_id": "call-1", "content": {"ok": True}},
    ]

    context = ActiveContextBuilder().build_message_context(messages)

    assert context.messages == messages
    assert context.messages is not messages
    assert context.report.sections["tool"]["message_count"] == 1
    assert context.report.active_chars == len("request") + len(str({"ok": True}))


def test_active_context_builder_defaults_missing_decision_to_keep() -> None:
    context = ActiveContextBuilder(
        budget=ContextBudget(total_chars=100),
    ).build_active_context(
        task="",
        candidates=[ContextCandidate("one", "source", "section", "value")],
        decisions=[],
    )

    assert context.sections == {"section": ["value"]}
    assert context.report.active_chars == len("value")
