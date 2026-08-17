from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class AgentStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_TOOL = "WAITING_TOOL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    PAUSED = "PAUSED"


class InvalidLifecycleTransition(RuntimeError):
    """Raised when an Agent status transition is not permitted."""


class LifecycleWaitCancelled(InterruptedError):
    """Raised when a lifecycle wait is cancelled by its cancellation event."""


@dataclass(frozen=True)
class LifecycleSnapshot:
    status: AgentStatus
    updated_at: str


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


_ALLOWED_TRANSITIONS: dict[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.CREATED: frozenset({AgentStatus.RUNNING, AgentStatus.CANCELLED}),
    AgentStatus.RUNNING: frozenset(
        {
            AgentStatus.WAITING_TOOL,
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
            AgentStatus.TIMEOUT,
            AgentStatus.PAUSED,
        }
    ),
    AgentStatus.WAITING_TOOL: frozenset(
        {
            AgentStatus.RUNNING,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
            AgentStatus.TIMEOUT,
            AgentStatus.PAUSED,
        }
    ),
    AgentStatus.PAUSED: frozenset(
        {AgentStatus.RUNNING, AgentStatus.FAILED, AgentStatus.CANCELLED}
    ),
    AgentStatus.COMPLETED: frozenset(),
    AgentStatus.FAILED: frozenset(),
    AgentStatus.CANCELLED: frozenset(),
    AgentStatus.TIMEOUT: frozenset(),
}


class AgentLifecycle:
    """Thread-safe state machine shared by Agent execution entry points."""

    def __init__(self, *, initial_status: AgentStatus = AgentStatus.CREATED) -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._status = initial_status
        self._updated_at = _now_iso()
        self._history: list[LifecycleSnapshot] = [
            LifecycleSnapshot(initial_status, self._updated_at)
        ]

    @property
    def status(self) -> AgentStatus:
        with self._lock:
            return self._status

    @property
    def history(self) -> tuple[LifecycleSnapshot, ...]:
        with self._lock:
            return tuple(self._history)

    def snapshot(self) -> LifecycleSnapshot:
        with self._lock:
            return LifecycleSnapshot(self._status, self._updated_at)

    def transition(self, new_status: AgentStatus) -> LifecycleSnapshot:
        new_status = AgentStatus(new_status)
        with self._lock:
            if new_status not in _ALLOWED_TRANSITIONS[self._status]:
                raise InvalidLifecycleTransition(
                    f"cannot transition from {self._status.value} to {new_status.value}"
                )
            self._status = new_status
            self._updated_at = _now_iso()
            snapshot = LifecycleSnapshot(new_status, self._updated_at)
            self._history.append(snapshot)
            self._condition.notify_all()
            return snapshot

    def wait(
        self,
        status: AgentStatus | None = None,
        timeout: float | None = None,
        *,
        cancel_event: threading.Event | None = None,
    ) -> LifecycleSnapshot:
        """Wait for a lifecycle transition or a target status.

        With ``status`` omitted, waits for the next transition after this
        method is called. With ``status`` supplied, returns when the lifecycle
        reaches that status. A timeout raises ``TimeoutError`` and an optional
        ``cancel_event`` raises ``LifecycleWaitCancelled`` when set.
        """
        target = AgentStatus(status) if status is not None else None
        end_at = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            baseline = len(self._history)
            while True:
                if target is not None and self._status is target:
                    return self.snapshot()
                if target is None and len(self._history) > baseline:
                    return self.snapshot()
                if target is None and self._status in {
                    AgentStatus.COMPLETED,
                    AgentStatus.FAILED,
                    AgentStatus.CANCELLED,
                    AgentStatus.TIMEOUT,
                }:
                    return self.snapshot()
                if cancel_event is not None and cancel_event.is_set():
                    raise LifecycleWaitCancelled("lifecycle wait cancelled")
                remaining = None if end_at is None else end_at - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError("lifecycle wait timed out")
                wait_for = remaining
                if cancel_event is not None:
                    wait_for = 0.05 if remaining is None else min(remaining, 0.05)
                self._condition.wait(timeout=wait_for)

    def start(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.RUNNING)

    def waiting_for_tool(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.WAITING_TOOL)

    def pause(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.PAUSED)

    def resume(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.RUNNING)

    def complete(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.COMPLETED)

    def fail(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.FAILED)

    def cancel(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.CANCELLED)

    def timeout(self) -> LifecycleSnapshot:
        return self.transition(AgentStatus.TIMEOUT)
