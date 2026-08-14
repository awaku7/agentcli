from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

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
    checkpoint: Optional[dict[str, Any]] = None


@dataclass
class TaskRuntime:
    asyncio_task: asyncio.Task[None] | None = None
    cancel_event: asyncio.Event | None = None
    locale: str = "en"
    lifecycle: AgentLifecycle = field(default_factory=AgentLifecycle)


@runtime_checkable
class TaskStore(Protocol):
    def create(self, rec: TaskRecord) -> None: ...

    def get(self, task_id: str) -> Optional[TaskRecord]: ...

    def list(self, *, limit: int = 100, offset: int = 0) -> list[TaskRecord]: ...

    def update(self, task_id: str, **kwargs: Any) -> Optional[TaskRecord]: ...

    def transition(
        self,
        task_id: str,
        expected: str | tuple[str, ...],
        new_status: str,
        **kwargs: Any,
    ) -> Optional[TaskRecord]: ...

    def recover_incomplete(self) -> list[TaskRecord]:
        """Mark tasks interrupted by process restart as failed."""
        ...

    def save_checkpoint(
        self, task_id: str, checkpoint: dict[str, Any]
    ) -> Optional[TaskRecord]: ...

    def load_checkpoint(self, task_id: str) -> Optional[dict[str, Any]]: ...


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
        """Atomically apply a permitted transition."""
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

    def recover_incomplete(self) -> list[TaskRecord]:
        recovered: list[TaskRecord] = []
        with self._lock:
            for rec in self.list(limit=100000):
                if rec.status in {
                    TaskStatus.IN_PROGRESS.value,
                    TaskStatus.CANCEL_REQUESTED.value,
                }:
                    updated = self.transition(
                        rec.id,
                        rec.status,
                        TaskStatus.FAILED.value,
                        error={"code": "TASK_INTERRUPTED_BY_RESTART"},
                    )
                    if updated is not None:
                        recovered.append(updated)
        return recovered

    def save_checkpoint(
        self, task_id: str, checkpoint: dict[str, Any]
    ) -> Optional[TaskRecord]:
        return self.update(task_id, checkpoint=dict(checkpoint))

    def load_checkpoint(self, task_id: str) -> Optional[dict[str, Any]]:
        record = self.get(task_id)
        return (
            dict(record.checkpoint)
            if record and record.checkpoint is not None
            else None
        )


class SQLiteTaskStore:
    """SQLite-backed TaskStore; runtime handles remain process-local."""

    def __init__(self, path: str) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._runtimes: dict[str, TaskRuntime] = {}
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_message TEXT,
                    output_message TEXT,
                    error TEXT,
                    checkpoint TEXT
                )
                """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "checkpoint" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN checkpoint TEXT")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _json(value: Any) -> str | None:
        return json.dumps(value, ensure_ascii=False) if value is not None else None

    @staticmethod
    def _loads(value: str | None) -> dict[str, Any] | None:
        return json.loads(value) if value else None

    @classmethod
    def _record(cls, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=str(row["id"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            status=str(row["status"]),
            input_message=cls._loads(row["input_message"]),
            output_message=cls._loads(row["output_message"]),
            error=cls._loads(row["error"]),
            checkpoint=(
                cls._loads(row["checkpoint"]) if "checkpoint" in row.keys() else None
            ),
        )

    def create(self, rec: TaskRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (id, created_at, updated_at, status, input_message, output_message, error, checkpoint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.id,
                    rec.created_at,
                    rec.updated_at,
                    rec.status,
                    self._json(rec.input_message),
                    self._json(rec.output_message),
                    self._json(rec.error),
                    self._json(rec.checkpoint),
                ),
            )

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return self._record(row) if row is not None else None

    def list(self, *, limit: int = 100, offset: int = 0) -> list[TaskRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at, id LIMIT ? OFFSET ?",
                (max(0, int(limit)), max(0, int(offset))),
            ).fetchall()
            return [self._record(row) for row in rows]

    def update(self, task_id: str, **kwargs: Any) -> Optional[TaskRecord]:
        if "status" in kwargs:
            return None
        allowed = {
            "created_at",
            "updated_at",
            "input_message",
            "output_message",
            "error",
            "checkpoint",
        }
        if not set(kwargs).issubset(allowed):
            raise ValueError("unsupported task update field")
        if not kwargs:
            return self.get(task_id)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                return None
            assignments: list[str] = []
            values: list[Any] = []
            for key, value in kwargs.items():
                assignments.append(f"{key} = ?")
                values.append(
                    self._json(value)
                    if key in {"input_message", "output_message", "error", "checkpoint"}
                    else value
                )
            assignments.append("updated_at = ?")
            values.append(_now_iso())
            values.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?", values
            )
            return self.get(task_id)

    def register_runtime(self, task_id: str, runtime: TaskRuntime) -> bool:
        with self._lock:
            if self.get(task_id) is None:
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
        expected_values = {expected} if isinstance(expected, str) else set(expected)
        allowed = {
            (TaskStatus.IN_PROGRESS.value, TaskStatus.SUCCEEDED.value),
            (TaskStatus.IN_PROGRESS.value, TaskStatus.FAILED.value),
            (TaskStatus.IN_PROGRESS.value, TaskStatus.CANCEL_REQUESTED.value),
            (TaskStatus.CANCEL_REQUESTED.value, TaskStatus.CANCELLED.value),
        }
        if not any(
            (expected_status, new_status) in allowed
            for expected_status in expected_values
        ):
            return None
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None or row["status"] not in expected_values:
                return None
            if (row["status"], new_status) not in allowed:
                return None
            updates = {"status": new_status, **kwargs, "updated_at": _now_iso()}
            assignments: list[str] = []
            values: list[Any] = []
            for key, value in updates.items():
                if key not in {
                    "status",
                    "updated_at",
                    "output_message",
                    "error",
                    "checkpoint",
                }:
                    raise ValueError("unsupported task transition field")
                assignments.append(f"{key} = ?")
                values.append(
                    self._json(value)
                    if key in {"output_message", "error", "checkpoint"}
                    else value
                )
            values.extend([task_id, row["status"]])
            conn.execute(
                f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ? AND status = ?",
                values,
            )
            return self._record(
                conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            )

    def recover_incomplete(self) -> list[TaskRecord]:
        recovered: list[TaskRecord] = []
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT id, status FROM tasks WHERE status IN (?, ?)",
                (TaskStatus.IN_PROGRESS.value, TaskStatus.CANCEL_REQUESTED.value),
            ).fetchall()
            for row in rows:
                now = _now_iso()
                error = self._json({"code": "TASK_INTERRUPTED_BY_RESTART"})
                conn.execute(
                    "UPDATE tasks SET status = ?, error = ?, updated_at = ? WHERE id = ? AND status = ?",
                    (TaskStatus.FAILED.value, error, now, row["id"], row["status"]),
                )
                # Reuse the transaction connection. Calling self.get() here
                # opens a second SQLite connection while BEGIN IMMEDIATE is
                # active, which self-deadlocks even in a single process.
                record_row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?",
                    (str(row["id"]),),
                ).fetchone()
                if record_row is not None:
                    recovered.append(self._record(record_row))
        return recovered

    def save_checkpoint(
        self, task_id: str, checkpoint: dict[str, Any]
    ) -> Optional[TaskRecord]:
        return self.update(task_id, checkpoint=dict(checkpoint))

    def load_checkpoint(self, task_id: str) -> Optional[dict[str, Any]]:
        record = self.get(task_id)
        return (
            dict(record.checkpoint)
            if record and record.checkpoint is not None
            else None
        )
