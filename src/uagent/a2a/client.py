from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ..env_utils import env_get


def _norm(v: str) -> str:
    return (v or "").strip()


class A2AClient:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout_sec: float = 60.0,
    ) -> None:
        self.base_url = _norm(
            base_url or env_get("UAGENT_A2A_BASE_URL", "http://127.0.0.1:8765")
        )
        self.token = _norm(token or env_get("UAGENT_A2A_TOKEN", ""))
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout_sec)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def _auth_headers(self) -> Dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def get_agent_card(self) -> Dict[str, Any]:
        r = self._client.get("/.well-known/agent-card.json")
        r.raise_for_status()
        return r.json()

    def get_extended_agent_card(self) -> Dict[str, Any]:
        r = self._client.get("/extendedAgentCard", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()

    def send_message(
        self, *, text: str, return_immediately: bool = False
    ) -> Dict[str, Any]:
        payload = {
            "message": {"role": "user", "content": text},
            "returnImmediately": bool(return_immediately),
        }
        r = self._client.post(
            "/message:send", json=payload, headers=self._auth_headers()
        )
        r.raise_for_status()
        return r.json()

    def get_task(self, task_id: str) -> Dict[str, Any]:
        r = self._client.get(f"/tasks/{task_id}", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()

    def list_tasks(self, *, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        r = self._client.get(
            "/tasks",
            params={"limit": int(limit), "offset": int(offset)},
            headers=self._auth_headers(),
        )
        r.raise_for_status()
        return r.json()

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        r = self._client.post(f"/tasks/{task_id}:cancel", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()
