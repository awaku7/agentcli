from __future__ import annotations

import pytest

from uagent.runtime.execution import (
    lifecycle_execution,
    mark_tool_running,
    mark_tool_waiting,
)
from uagent.runtime.lifecycle import AgentStatus, LifecycleSnapshot


def test_lifecycle_execution_completes_on_success() -> None:
    with lifecycle_execution() as lifecycle:
        assert lifecycle.status is AgentStatus.RUNNING

    assert lifecycle.status is AgentStatus.COMPLETED


def test_lifecycle_execution_notifies_transition_callback() -> None:
    snapshots: list[LifecycleSnapshot] = []

    with lifecycle_execution(on_transition=snapshots.append):
        pass

    assert [item.status for item in snapshots] == [
        AgentStatus.RUNNING,
        AgentStatus.COMPLETED,
    ]


def test_lifecycle_execution_fails_on_exception() -> None:
    with pytest.raises(ValueError):
        with lifecycle_execution() as lifecycle:
            assert lifecycle.status is AgentStatus.RUNNING
            raise ValueError("boom")

    assert lifecycle.status is AgentStatus.FAILED


def test_lifecycle_execution_cancels_on_keyboard_interrupt() -> None:
    with pytest.raises(KeyboardInterrupt):
        with lifecycle_execution() as lifecycle:
            raise KeyboardInterrupt()

    assert lifecycle.status is AgentStatus.CANCELLED


def test_lifecycle_execution_can_mark_tool_waiting() -> None:
    with lifecycle_execution() as lifecycle:
        mark_tool_waiting()
        assert lifecycle.status is AgentStatus.WAITING_TOOL
        mark_tool_running()
        assert lifecycle.status is AgentStatus.RUNNING

    assert lifecycle.status is AgentStatus.COMPLETED


def test_lifecycle_execution_emits_specific_events(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(
        "uagent.runtime.execution.log_event",
        lambda event, **fields: events.append(event),
    )

    with lifecycle_execution():
        mark_tool_waiting()
        mark_tool_running()

    assert events == [
        "agent.lifecycle.changed",
        "agent.created",
        "agent.lifecycle.changed",
        "agent.started",
        "agent.lifecycle.changed",
        "agent.waiting_tool",
        "agent.lifecycle.changed",
        "agent.started",
        "agent.lifecycle.changed",
        "agent.completed",
    ]
