"""Remote Agent Runtime adapter for A2A endpoints."""

from __future__ import annotations

from typing import Any

from ..a2a.client import A2AClient


class RemoteAgentRuntime:
    """Submit and inspect tasks on a remote A2A agent."""

    def __init__(self, *, base_url: str, token: str | None = None, credential_store: Any = None) -> None:
        self.client = A2AClient(base_url=base_url, token=token, credential_store=credential_store)

    def close(self) -> None:
        self.client.close()

    def submit(self, text: str, *, return_immediately: bool = True) -> dict[str, Any]:
        return self.client.send_message(text=text, return_immediately=return_immediately)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.client.get_task(task_id)


__all__ = ["RemoteAgentRuntime"]
