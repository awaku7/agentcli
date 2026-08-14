"""Remote Agent Runtime adapter for A2A endpoints."""

from __future__ import annotations

import time
from typing import Any

from ..a2a.client import A2AClient


class RemoteAgentRuntime:
    """Submit and inspect tasks on a remote A2A agent."""

    def __init__(self, *, base_url: str, token: str | None = None, credential_store: Any = None) -> None:
        self.client = A2AClient(base_url=base_url, token=token, credential_store=credential_store)

    def close(self) -> None:
        self.client.close()

    def submit(self, text: str, *, return_immediately: bool = True, retries: int = 2) -> dict[str, Any]:
        return self._retry(lambda: self.client.send_message(text=text, return_immediately=return_immediately), retries)

    def get_task(self, task_id: str, *, retries: int = 2) -> dict[str, Any]:
        return self._retry(lambda: self.client.get_task(task_id), retries)

    def cancel(self, task_id: str, *, retries: int = 2) -> dict[str, Any]:
        return self._retry(lambda: self.client.cancel_task(task_id), retries)

    def list_tasks(self, *, limit: int = 100, offset: int = 0, retries: int = 2) -> dict[str, Any]:
        return self._retry(lambda: self.client.list_tasks(limit=limit, offset=offset), retries)

    def wait(self, task_id: str, *, timeout: float = 300, interval: float = 1.0) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            task = self.get_task(task_id)
            status = str((task.get("task") or task).get("status") or "").upper()
            if status in {"SUCCEEDED", "FAILED", "CANCELLED", "COMPLETED", "TIMEOUT"}:
                return task
            if time.monotonic() >= deadline:
                raise TimeoutError("remote A2A task polling timed out")
            time.sleep(max(0.05, interval))

    @staticmethod
    def _retry(operation: Any, retries: int) -> Any:
        attempts = max(0, int(retries)) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(min(2.0, 0.25 * (2**attempt)))
        assert last_error is not None
        raise last_error


__all__ = ["RemoteAgentRuntime"]
