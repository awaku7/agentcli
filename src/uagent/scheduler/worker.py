from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable

from .run_store import SchedulerRunStore


class SchedulerWorker:
    """Execute queued scheduler runs through an injected callable."""

    def __init__(self, store: SchedulerRunStore | None = None) -> None:
        self.store = store or SchedulerRunStore()

    def execute(
        self,
        run_id: str,
        executor: Callable[[dict[str, Any]], Any],
        *,
        timeout_sec: int = 0,
        retry_limit: int = 0,
        retry_backoff_sec: int = 0,
    ) -> Any:
        run = self.store.get(run_id)
        if run is None:
            raise KeyError(f"scheduler run not found: {run_id}")
        if run.status in {"success", "cancelled"}:
            return run.result

        last_error = ""
        for attempt in range(max(0, int(retry_limit)) + 1):
            self.store.start(run_id)
            current = self.store.get(run_id)
            payload = dict((current.metadata if current else {}) or {})
            payload.update({"run_id": run_id, "schedule_id": run.schedule_id})
            try:
                if float(timeout_sec or 0) > 0:
                    pool = ThreadPoolExecutor(max_workers=1)
                    future = pool.submit(executor, payload)
                    try:
                        result = future.result(timeout=float(timeout_sec))
                    finally:
                        pool.shutdown(wait=False, cancel_futures=True)
                else:
                    result = executor(payload)
                self.store.finish(run_id, result=result)
                return result
            except FutureTimeout:
                last_error = f"scheduler run timed out after {timeout_sec} seconds"
                status = "timeout"
            except Exception as exc:
                last_error = str(exc)
                status = "failed"

            if attempt < int(retry_limit):
                if int(retry_backoff_sec or 0) > 0:
                    time.sleep(int(retry_backoff_sec))
                continue
            self.store.finish(run_id, status=status, error=last_error)
            raise RuntimeError(last_error)

        raise RuntimeError(last_error or "scheduler run failed")


__all__ = ["SchedulerWorker"]
