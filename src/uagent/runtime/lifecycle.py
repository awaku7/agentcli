from __future__ import annotations

import threading
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


@dataclass(frozen=True)
class LifecycleSnapshot:
    status: AgentStatus
    updated_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
            return snapshot

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
