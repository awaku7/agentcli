"""Bounded server-side sessions for verified OIDC identities."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import secrets
import threading
import time
from typing import Callable

from ..runtime.identity_context import IdentityContext, IdentityResolutionError


@dataclass(frozen=True)
class _StoredSession:
    identity: IdentityContext
    expires_at: float
    configuration_fingerprint: str
    project_id: str = ""


class OIDCSessionStore:
    """Keep opaque browser tokens separate from verified identity data."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 8 * 60 * 60,
        max_sessions: int = 4096,
        clock: Callable[[], float] = time.monotonic,
        configuration_fingerprint: Callable[[], str] | None = None,
        ttl_seconds_provider: Callable[[], float] | None = None,
        max_sessions_provider: Callable[[], int] | None = None,
    ) -> None:
        if ttl_seconds <= 0 or max_sessions <= 0:
            raise ValueError("OIDC session limits must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._ttl_seconds_provider = ttl_seconds_provider
        self._max_sessions_provider = max_sessions_provider
        self._clock = clock
        self._configuration_fingerprint = (
            configuration_fingerprint or _authentication_configuration_fingerprint
        )
        self._lock = threading.Lock()
        self._sessions: dict[str, _StoredSession] = {}

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(
        self,
        identity: IdentityContext,
        *,
        expected_configuration_fingerprint: str | None = None,
        project_id: str = "",
    ) -> str:
        if not identity.authenticated:
            raise ValueError("only authenticated identities may create sessions")
        token = secrets.token_urlsafe(32)
        observed_configuration_fingerprint = self._configuration_fingerprint()
        if (
            expected_configuration_fingerprint is not None
            and observed_configuration_fingerprint != expected_configuration_fingerprint
        ):
            raise IdentityResolutionError("authentication configuration changed")
        ttl_seconds = (
            self._ttl_seconds_provider()
            if self._ttl_seconds_provider is not None
            else self._ttl_seconds
        )
        max_sessions = (
            self._max_sessions_provider()
            if self._max_sessions_provider is not None
            else self._max_sessions
        )
        if ttl_seconds <= 0 or max_sessions <= 0:
            raise ValueError("OIDC session limits must be positive")
        with self._lock:
            # The configuration may rotate while waiting for the store lock.
            # Always use the post-lock value for pruning and for the session
            # being created; otherwise a valid session from the new revision
            # could be pruned as stale or a new session could be bound to the
            # old revision.
            configuration_fingerprint = self._configuration_fingerprint()
            if (
                expected_configuration_fingerprint is not None
                and configuration_fingerprint != expected_configuration_fingerprint
            ):
                raise IdentityResolutionError("authentication configuration changed")
            now = self._clock()
            self._prune(now, configuration_fingerprint)
            if len(self._sessions) >= max_sessions:
                raise RuntimeError("OIDC session capacity reached")
            self._sessions[self._key(token)] = _StoredSession(
                identity=identity,
                expires_at=now + ttl_seconds,
                configuration_fingerprint=configuration_fingerprint,
                project_id=str(project_id or "").strip(),
            )
        return token

    def resolve(self, token: str) -> IdentityContext | None:
        if not token:
            return None
        key = self._key(token)
        # Read the authoritative configuration revision while holding the
        # store lock so a rotation during lock acquisition cannot make us
        # prune with a stale fingerprint.
        with self._lock:
            configuration_fingerprint = self._configuration_fingerprint()
            now = self._clock()
            self._prune(now, configuration_fingerprint)
            stored = self._sessions.get(key)
            if stored is None:
                return None
            # Verify the entry against the same post-lock snapshot before
            # returning its identity.  A mismatched entry must never be
            # usable even if pruning is changed or extended later.
            if stored.configuration_fingerprint != configuration_fingerprint:
                self._sessions.pop(key, None)
                return None
            return stored.identity

    def project_id(self, token: str) -> str | None:
        if not token:
            return None
        key = self._key(token)
        with self._lock:
            configuration_fingerprint = self._configuration_fingerprint()
            self._prune(self._clock(), configuration_fingerprint)
            stored = self._sessions.get(key)
            if (
                stored is None
                or stored.configuration_fingerprint != configuration_fingerprint
            ):
                return None
            return stored.project_id or None

    def bind_project(self, token: str, project_id: str) -> bool:
        project_id = str(project_id or "").strip()
        if not token or not project_id:
            raise ValueError("token and project_id are required")
        key = self._key(token)
        with self._lock:
            configuration_fingerprint = self._configuration_fingerprint()
            self._prune(self._clock(), configuration_fingerprint)
            stored = self._sessions.get(key)
            if (
                stored is None
                or stored.configuration_fingerprint != configuration_fingerprint
            ):
                return False
            self._sessions[key] = replace(stored, project_id=project_id)
            return True

    def revoke(self, token: str) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(self._key(token), None)

    def revoke_all(self) -> int:
        """Invalidate all browser sessions and return the number removed."""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def active_count(self) -> int:
        with self._lock:
            # Read the revision under the same lock used for pruning so a
            # session created under a newer revision cannot be removed using
            # a stale pre-lock fingerprint.
            configuration_fingerprint = self._configuration_fingerprint()
            self._prune(self._clock(), configuration_fingerprint)
            return len(self._sessions)

    def _prune(self, now: float, configuration_fingerprint: str) -> None:
        for key, stored in list(self._sessions.items()):
            if (
                now >= stored.expires_at
                or stored.configuration_fingerprint != configuration_fingerprint
            ):
                del self._sessions[key]


def _authentication_configuration_fingerprint() -> str:
    from ..runtime.auth_management import authentication_configuration_fingerprint

    return authentication_configuration_fingerprint()


def _configured_session_ttl() -> int:
    from ..runtime.auth_management import positive_integer_setting

    return positive_integer_setting("UAGENT_OIDC_SESSION_TTL", 28800)


def _configured_session_capacity() -> int:
    from ..runtime.auth_management import positive_integer_setting

    return positive_integer_setting("UAGENT_OIDC_SESSION_MAX", 4096)


_DEFAULT_SESSION_STORE: OIDCSessionStore | None = None
_DEFAULT_SESSION_LOCK = threading.Lock()


def get_oidc_session_store() -> OIDCSessionStore:
    """Return the process-local server-side OIDC session store."""
    global _DEFAULT_SESSION_STORE
    if _DEFAULT_SESSION_STORE is None:
        with _DEFAULT_SESSION_LOCK:
            if _DEFAULT_SESSION_STORE is None:
                _DEFAULT_SESSION_STORE = OIDCSessionStore(
                    ttl_seconds_provider=_configured_session_ttl,
                    max_sessions_provider=_configured_session_capacity,
                )
    return _DEFAULT_SESSION_STORE


__all__ = ["OIDCSessionStore", "get_oidc_session_store"]
