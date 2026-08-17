from __future__ import annotations

import threading
import time

import pytest

from uagent.runtime.lifecycle import (
    AgentLifecycle,
    AgentStatus,
    InvalidLifecycleTransition,
    LifecycleWaitCancelled,
)


def test_lifecycle_starts_and_completes() -> None:
    lifecycle = AgentLifecycle()

    assert lifecycle.status is AgentStatus.CREATED
    assert lifecycle.start().status is AgentStatus.RUNNING
    assert lifecycle.complete().status is AgentStatus.COMPLETED
    assert lifecycle.snapshot().status is AgentStatus.COMPLETED


def test_lifecycle_supports_tool_waiting_and_resume() -> None:
    lifecycle = AgentLifecycle()

    lifecycle.start()
    assert lifecycle.waiting_for_tool().status is AgentStatus.WAITING_TOOL
    assert lifecycle.resume().status is AgentStatus.RUNNING
    assert lifecycle.complete().status is AgentStatus.COMPLETED


def test_lifecycle_supports_pause_and_resume() -> None:
    lifecycle = AgentLifecycle()

    lifecycle.start()
    assert lifecycle.pause().status is AgentStatus.PAUSED
    assert lifecycle.resume().status is AgentStatus.RUNNING


def test_lifecycle_cancellation_is_terminal() -> None:
    lifecycle = AgentLifecycle()

    lifecycle.start()
    assert lifecycle.cancel().status is AgentStatus.CANCELLED

    with pytest.raises(InvalidLifecycleTransition):
        lifecycle.resume()


def test_lifecycle_rejects_invalid_transition() -> None:
    lifecycle = AgentLifecycle()

    with pytest.raises(InvalidLifecycleTransition):
        lifecycle.complete()


def test_lifecycle_supports_failure_and_timeout() -> None:
    failed = AgentLifecycle()
    failed.start()
    assert failed.fail().status is AgentStatus.FAILED

    timed_out = AgentLifecycle()
    timed_out.start()
    assert timed_out.timeout().status is AgentStatus.TIMEOUT


def test_lifecycle_keeps_transition_history() -> None:
    lifecycle = AgentLifecycle()

    lifecycle.start()
    lifecycle.waiting_for_tool()
    lifecycle.resume()
    lifecycle.complete()

    assert [item.status for item in lifecycle.history] == [
        AgentStatus.CREATED,
        AgentStatus.RUNNING,
        AgentStatus.WAITING_TOOL,
        AgentStatus.RUNNING,
        AgentStatus.COMPLETED,
    ]


def test_lifecycle_waits_for_target_status() -> None:
    lifecycle = AgentLifecycle()
    result: list[AgentStatus] = []

    def waiter() -> None:
        result.append(lifecycle.wait(AgentStatus.COMPLETED, timeout=1).status)

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.02)
    lifecycle.start()
    lifecycle.complete()
    thread.join(timeout=1)

    assert result == [AgentStatus.COMPLETED]


def test_lifecycle_wait_timeout_and_cancel() -> None:
    lifecycle = AgentLifecycle()

    with pytest.raises(TimeoutError):
        lifecycle.wait(AgentStatus.COMPLETED, timeout=0.01)

    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(LifecycleWaitCancelled):
        lifecycle.wait(AgentStatus.COMPLETED, cancel_event=cancelled)
