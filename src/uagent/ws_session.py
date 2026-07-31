from __future__ import annotations

"""
Session manager for WebSocket server.
Shares the same state directory as the regular uag CLI sessions.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from uagent.utils.paths import get_state_dir


class WsSessionManager:
    """WebSocket session manager with CLI session compatibility."""

    def __init__(self):
        self.sessions_dir: Path = get_state_dir() / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._current_id: str | None = None

    @property
    def current_id(self) -> str | None:
        return self._current_id

    def create(self) -> str:
        """Create a new session and return its ID."""
        session_id = uuid.uuid4().hex[:12]
        session_path = self.sessions_dir / f"{session_id}.json"
        session_data: dict[str, Any] = {
            "id": session_id,
            "created": datetime.now(timezone.utc).isoformat(),
            "messages": [],
            "context": {},
        }
        session_path.write_text(
            json.dumps(session_data, ensure_ascii=False), encoding="utf-8"
        )
        self._current_id = session_id
        return session_id

    def list_sessions(self) -> list[dict[str, Any]]:
        """List available sessions, newest first."""
        sessions: list[dict[str, Any]] = []
        for f in sorted(
            self.sessions_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                messages = data.get("messages", [])
                last_msg = messages[-1] if messages else {}
                sessions.append(
                    {
                        "id": data["id"],
                        "created": data.get("created", ""),
                        "message_count": len(messages),
                        "preview": (last_msg.get("content") or "")[:120],
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def load(self, index: int = 0) -> dict[str, Any] | None:
        """Load a session by index (0 = most recent)."""
        sessions = self.list_sessions()
        if not sessions:
            return None
        if index < 0 or index >= len(sessions):
            return None
        session_path = self.sessions_dir / f"{sessions[index]['id']}.json"
        if not session_path.exists():
            return None
        self._current_id = sessions[index]["id"]
        return json.loads(session_path.read_text(encoding="utf-8"))

    def delete(self, session_id: str) -> bool:
        """Delete a session by ID. Returns True if deleted."""
        session_path = self.sessions_dir / f"{session_id}.json"
        if session_path.exists():
            session_path.unlink()
            if self._current_id == session_id:
                self._current_id = None
            return True
        return False

    def save_message(
        self, role: str, content: str, session_id: str | None = None
    ) -> None:
        """Append a message to the current or specified session."""
        sid = session_id or self._current_id
        if not sid:
            return
        session_path = self.sessions_dir / f"{sid}.json"
        if not session_path.exists():
            return
        data = json.loads(session_path.read_text(encoding="utf-8"))
        data.setdefault("messages", []).append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        session_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
