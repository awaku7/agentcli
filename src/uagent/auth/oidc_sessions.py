"""Bounded server-side sessions for verified OIDC identities."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import secrets
import threading
import time
from typing import Callable

from ..env_utils import env_get
from ..runtime.identity_context import IdentityContext


@dataclass(frozen=True)
class _StoredSession:
    identity: IdentityContext
    expires_at: float


class OIDCSessionStore:
    """Keep opaque browser tokens separate from verified identity data."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 8 * 60 * 60,
        max_sessions: int = 4096,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_sessions <= 0:
            raise ValueError("OIDC session limits must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, _StoredSession] = {}

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, identity: IdentityContext) -> str:
        if not identity.authenticated:
            raise ValueError("only authenticated identities may create sessions")
        token = secrets.token_urlsafe(32)
        with self._lock:
            now = self._clock()
            self._prune(now)
            if len(self._sessions) >= self._max_sessions:
                raise RuntimeError("OIDC session capacity reached")
            self._sessions[self._key(token)] = _StoredSession(
                identity=identity,
                expires_at=now + self._ttl_seconds,
            )
        return token

    def resolve(self, token: str) -> IdentityContext | None:
        if not token:
            return None
        key = self._key(token)
        with self._lock:
            now = self._clock()
            stored = self._sessions.get(key)
            if stored is None:
                self._prune(now)
                return None
            if now >= stored.expires_at:
                del self._sessions[key]
                return None
            return stored.identity

    def revoke(self, token: str) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(self._key(token), None)

    def _prune(self, now: float) -> None:
        for key, stored in list(self._sessions.items()):
            if now >= stored.expires_at:
                del self._sessions[key]


_DEFAULT_SESSION_STORE: OIDCSessionStore | None = None
_DEFAULT_SESSION_LOCK = threading.Lock()


def get_oidc_session_store() -> OIDCSessionStore:
    """Return the process-local server-side OIDC session store."""
    global _DEFAULT_SESSION_STORE
    if _DEFAULT_SESSION_STORE is None:
        with _DEFAULT_SESSION_LOCK:
            if _DEFAULT_SESSION_STORE is None:
                try:
                    ttl = float(env_get("UAGENT_OIDC_SESSION_TTL", "28800"))
                except (TypeError, ValueError):
                    ttl = 28800.0
                try:
                    capacity = int(env_get("UAGENT_OIDC_SESSION_MAX", "4096"))
                except (TypeError, ValueError):
                    capacity = 4096
                _DEFAULT_SESSION_STORE = OIDCSessionStore(
                    ttl_seconds=ttl,
                    max_sessions=capacity,
                )
    return _DEFAULT_SESSION_STORE


__all__ = ["OIDCSessionStore", "get_oidc_session_store"]
