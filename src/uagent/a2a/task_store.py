from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class TaskRecord:
    id: str
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    status: str = "IN_PROGRESS"  # IN_PROGRESS | SUCCEEDED | FAILED | CANCELLED
    input_message: Optional[Dict[str, Any]] = None
    output_message: Optional[Dict[str, Any]] = None

    error: Optional[Dict[str, Any]] = None


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, TaskRecord] = {}
        self._order: List[str] = []

    def create(self, rec: TaskRecord) -> None:
        with self._lock:
            self._tasks[rec.id] = rec
            self._order.append(rec.id)

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> List[TaskRecord]:
        with self._lock:
            ids = self._order[offset : offset + limit]
            return [self._tasks[i] for i in ids if i in self._tasks]

    def update(self, task_id: str, **kwargs: Any) -> Optional[TaskRecord]:
        with self._lock:
            rec = self._tasks.get(task_id)
            if not rec:
                return None
            for k, v in kwargs.items():
                setattr(rec, k, v)
            rec.updated_at = _now_iso()
            return rec
