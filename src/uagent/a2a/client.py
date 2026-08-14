from __future__ import annotations

from typing import Any, Optional

try:
    import httpx
except ImportError:
    from .._pip_auto import install_with_status as _install_httpx

    _install_httpx("httpx")
    import httpx

from ..auth import CredentialKind, CredentialStore, get_default_credential_store, resolve_credential_secret
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
        credential_store: CredentialStore | None = None,
        credential_name: str = "a2a/default",
    ) -> None:
        self.base_url = _norm(
            base_url or env_get("UAGENT_A2A_BASE_URL", "http://127.0.0.1:8765")
        )
        self.credential_store = credential_store or get_default_credential_store()
        self.token = _norm(
            token
            or resolve_credential_secret(
                credential_name,
                kind=CredentialKind.A2A,
                store=self.credential_store,
                env_names=("UAGENT_A2A_TOKEN",),
            )
            or ""
        )
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout_sec)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def _auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def get_agent_card(self) -> dict[str, Any]:
        r = self._client.get("/.well-known/agent-card.json")
        r.raise_for_status()
        return r.json()

    def get_extended_agent_card(self) -> dict[str, Any]:
        r = self._client.get("/extendedAgentCard", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()

    def send_message(
        self, *, text: str, return_immediately: bool = False
    ) -> dict[str, Any]:
        payload = {
            "message": {"role": "user", "content": text},
            "returnImmediately": bool(return_immediately),
        }
        r = self._client.post(
            "/message:send", json=payload, headers=self._auth_headers()
        )
        r.raise_for_status()
        return r.json()

    def get_task(self, task_id: str) -> dict[str, Any]:
        r = self._client.get(f"/tasks/{task_id}", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()

    def list_tasks(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        r = self._client.get(
            "/tasks",
            params={"limit": int(limit), "offset": int(offset)},
            headers=self._auth_headers(),
        )
        r.raise_for_status()
        return r.json()

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        r = self._client.post(f"/tasks/{task_id}:cancel", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()

    def get_checkpoint(self, task_id: str) -> dict[str, Any]:
        r = self._client.get(f"/tasks/{task_id}/checkpoint", headers=self._auth_headers())
        r.raise_for_status()
        return r.json()

    def save_checkpoint(self, task_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post(
            f"/tasks/{task_id}/checkpoint",
            json={"checkpoint": checkpoint},
            headers=self._auth_headers(),
        )
        r.raise_for_status()
        return r.json()


    def subscribe_task(self, task_id: str):
        """Yield task events from the remote SSE subscription endpoint."""
        import json

        with self._client.stream(
            "POST", f"/tasks/{task_id}:subscribe", headers=self._auth_headers()
        ) as response:
            response.raise_for_status()
            data: list[str] = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data.append(line[6:])
                elif not line and data:
                    payload = "\n".join(data)
                    data.clear()
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        continue
