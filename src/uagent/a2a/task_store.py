from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from ..runtime.lifecycle import AgentLifecycle


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class TaskStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskRecord:
    id: str
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    status: str = TaskStatus.IN_PROGRESS.value
    input_message: Optional[dict[str, Any]] = None
    output_message: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


@dataclass
class TaskRuntime:
    asyncio_task: asyncio.Task[None] | None = None
    cancel_event: asyncio.Event | None = None
    locale: str = "en"
    lifecycle: AgentLifecycle = field(default_factory=AgentLifecycle)


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, TaskRecord] = {}
        self._runtimes: dict[str, TaskRuntime] = {}
        self._order: list[str] = []

    def create(self, rec: TaskRecord) -> None:
        with self._lock:
            self._tasks[rec.id] = rec
            self._order.append(rec.id)

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[TaskRecord]:
        with self._lock:
            ids = self._order[offset : offset + limit]
            return [self._tasks[i] for i in ids if i in self._tasks]

    def update(self, task_id: str, **kwargs: Any) -> Optional[TaskRecord]:
        with self._lock:
            rec = self._tasks.get(task_id)
            if not rec:
                return None
            # Status changes must go through transition() so terminal results
            # cannot be overwritten by a late worker.
            if "status" in kwargs and kwargs["status"] != rec.status:
                return None
            for k, v in kwargs.items():
                setattr(rec, k, v)
            rec.updated_at = _now_iso()
            return rec

    def register_runtime(self, task_id: str, runtime: TaskRuntime) -> bool:
        with self._lock:
            if task_id not in self._tasks:
                return False
            self._runtimes[task_id] = runtime
            return True

    def runtime(self, task_id: str) -> TaskRuntime | None:
        with self._lock:
            return self._runtimes.get(task_id)

    def transition(
        self,
        task_id: str,
        expected: str | tuple[str, ...],
        new_status: str,
        **kwargs: Any,
    ) -> Optional[TaskRecord]:
        """Atomically apply a permitted transition.

        A late worker completion cannot overwrite a cancellation because terminal
        transitions only compare-and-set from the expected current state.
        """
        expected_values = {expected} if isinstance(expected, str) else set(expected)
        allowed = {
            (TaskStatus.IN_PROGRESS.value, TaskStatus.SUCCEEDED.value),
            (TaskStatus.IN_PROGRESS.value, TaskStatus.FAILED.value),
            (TaskStatus.IN_PROGRESS.value, TaskStatus.CANCEL_REQUESTED.value),
            (TaskStatus.CANCEL_REQUESTED.value, TaskStatus.CANCELLED.value),
        }
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None or rec.status not in expected_values:
                return None
            if (rec.status, new_status) not in allowed:
                return None
            rec.status = new_status
            for k, v in kwargs.items():
                setattr(rec, k, v)
            rec.updated_at = _now_iso()
            return rec
