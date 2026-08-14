"""Small shared-file lease for single-leader distributed coordination."""

from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path


class LeaseUnavailable(RuntimeError):
    """Another live runtime owns the lease."""


class LeaderLease:
    """Best-effort atomic lease suitable for a shared filesystem."""

    def __init__(
        self, path: str | Path, *, ttl: float = 30.0, owner: str | None = None
    ) -> None:
        self.path = Path(path)
        self.ttl = max(1.0, float(ttl))
        self.owner = owner or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        payload = {"owner": self.owner, "expires_at": now + self.ttl}
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            return True
        except FileExistsError:
            if self._expired(now):
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                return self.acquire()
            return False

    def renew(self) -> bool:
        current = self._read()
        if not current or current.get("owner") != self.owner:
            return False
        self.path.write_text(
            json.dumps({"owner": self.owner, "expires_at": time.time() + self.ttl}),
            encoding="utf-8",
        )
        return True

    def release(self) -> bool:
        current = self._read()
        if not current or current.get("owner") != self.owner:
            return False
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True

    def _read(self) -> dict[str, object] | None:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    def _expired(self, now: float) -> bool:
        current = self._read()
        try:
            return not current or float(current.get("expires_at", 0)) <= now
        except (TypeError, ValueError):
            return True


__all__ = ["LeaderLease", "LeaseUnavailable"]
