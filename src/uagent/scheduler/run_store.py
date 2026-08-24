from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from ..utils.paths import get_schedules_json_path
from .models import format_iso_datetime, utc_now

_LOCK = threading.RLock()


VALID_RUN_STATUSES = {"queued", "running", "success", "failed", "timeout", "cancelled"}


@dataclass
class SchedulerRun:
    run_id: str
    schedule_id: str
    status: str = "queued"
    attempt: int = 0
    idempotency_key: str = ""
    created_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    error: str = ""
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "SchedulerRun":
        self.run_id = str(self.run_id or "").strip() or str(uuid4())
        self.schedule_id = str(self.schedule_id or "").strip()
        self.status = str(self.status or "queued").strip().lower()
        if self.status not in VALID_RUN_STATUSES:
            raise ValueError(f"invalid scheduler run status: {self.status}")
        self.attempt = max(0, int(self.attempt or 0))
        self.idempotency_key = str(self.idempotency_key or "").strip()
        if not self.created_at:
            self.created_at = format_iso_datetime(utc_now())
        if not isinstance(self.metadata, dict):
            self.metadata = {}
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "schedule_id": self.schedule_id,
            "status": self.status,
            "attempt": self.attempt,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "result": self.result,
            "metadata": self.metadata,
        }


class SchedulerRunStore:
    """Durable execution records for scheduled jobs.

    This store deliberately does not execute jobs.  It provides the persistent
    run lifecycle that a future queue/worker integration can use.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        default = get_schedules_json_path().with_name("scheduler_runs.json")
        self.path = Path(path or default)

    def _read(self) -> list[SchedulerRun]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw.get("runs", []) if isinstance(raw, dict) else raw
            return [SchedulerRun(**item).normalized() for item in items if isinstance(item, dict)]
        except Exception:
            # Preserve the evidence instead of silently overwriting a corrupt
            # history on the next create/update operation.
            try:
                quarantine = self.path.with_name(
                    f"{self.path.name}.corrupt.{int(time.time())}"
                )
                os.replace(self.path, quarantine)
            except OSError:
                pass
            return []

    def _write(self, runs: list[SchedulerRun]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": 1, "runs": [run.normalized().as_dict() for run in runs]},
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        fd, name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.remove(name)

    def create(
        self,
        schedule_id: str,
        *,
        idempotency_key: str = "",
        metadata: Optional[dict[str, Any]] = None,
        run_id: str = "",
    ) -> SchedulerRun:
        with _LOCK:
            runs = self._read()
            key = str(idempotency_key or "").strip()
            if key:
                for existing in reversed(runs):
                    if existing.idempotency_key == key:
                        return existing
            run = SchedulerRun(
                run_id=run_id,
                schedule_id=schedule_id,
                idempotency_key=key,
                metadata=dict(metadata or {}),
            ).normalized()
            runs.append(run)
            self._write(runs)
            return run

    def get(self, run_id: str) -> Optional[SchedulerRun]:
        with _LOCK:
            return next((r for r in self._read() if r.run_id == str(run_id)), None)

    def list(self, schedule_id: str = "", limit: int = 100) -> list[SchedulerRun]:
        with _LOCK:
            runs = self._read()
            sid = str(schedule_id or "").strip()
            if sid:
                runs = [run for run in runs if run.schedule_id == sid]
            return list(reversed(runs[-max(1, int(limit or 100)) :]))

    def update(self, run_id: str, **changes: Any) -> SchedulerRun:
        with _LOCK:
            runs = self._read()
            for run in runs:
                if run.run_id == str(run_id):
                    for key, value in changes.items():
                        if not hasattr(run, key):
                            raise ValueError(f"unknown scheduler run field: {key}")
                        setattr(run, key, value)
                    run.normalized()
                    self._write(runs)
                    return run
        raise KeyError(f"scheduler run not found: {run_id}")

    def claim(self, run_id: str) -> SchedulerRun | None:
        """Atomically claim a queued run within this process.

        Returning ``None`` means another worker already claimed or completed it.
        """
        with _LOCK:
            runs = self._read()
            for run in runs:
                if run.run_id != str(run_id):
                    continue
                if run.status != "queued":
                    return None
                run.status = "running"
                run.attempt += 1
                run.started_at = format_iso_datetime(utc_now())
                run.normalized()
                self._write(runs)
                return run
        raise KeyError(f"scheduler run not found: {run_id}")

    def start(self, run_id: str) -> SchedulerRun:
        """Start a run, retaining the legacy API for direct callers."""
        claimed = self.claim(run_id)
        if claimed is None:
            current = self.get(run_id)
            if current is None:
                raise KeyError(f"scheduler run not found: {run_id}")
            return current
        return claimed

    def finish(self, run_id: str, *, result: Any = None, status: str = "success", error: str = "") -> SchedulerRun:
        if status not in {"success", "failed", "timeout", "cancelled"}:
            raise ValueError(f"invalid terminal status: {status}")
        return self.update(
            run_id,
            status=status,
            result=result,
            error=str(error or ""),
            finished_at=format_iso_datetime(utc_now()),
        )


__all__ = ["SchedulerRun", "SchedulerRunStore", "VALID_RUN_STATUSES"]
