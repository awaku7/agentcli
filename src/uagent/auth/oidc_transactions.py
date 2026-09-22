"""Single-use OIDC authorization transactions.

A future Web login endpoint supplies an opaque browser-session binding. Tokens
and authenticated principals are deliberately outside this transaction store.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import secrets
import threading
import time
from typing import Callable

from .pkce import code_challenge_s256, generate_code_verifier, generate_state


@dataclass(frozen=True)
class OIDCAuthorizationTransaction:
    state: str
    nonce: str
    code_verifier: str
    code_challenge: str


@dataclass(frozen=True)
class _PendingTransaction:
    transaction: OIDCAuthorizationTransaction
    browser_binding: str
    expires_at: float


class OIDCTransactionStore:
    """Bounded, short-lived state/nonce/PKCE records tied to one browser."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        max_pending: int = 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_pending <= 0:
            raise ValueError("OIDC transaction limits must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_pending = max_pending
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingTransaction] = {}

    def begin(self, browser_binding: str) -> OIDCAuthorizationTransaction:
        """Issue a fresh transaction for a server-managed browser binding."""
        if not browser_binding:
            raise ValueError("browser binding is required")
        verifier = generate_code_verifier()
        transaction = OIDCAuthorizationTransaction(
            state=generate_state(),
            nonce=secrets.token_urlsafe(32),
            code_verifier=verifier,
            code_challenge=code_challenge_s256(verifier),
        )
        with self._lock:
            now = self._clock()
            self._prune(now)
            if len(self._pending) >= self._max_pending:
                raise RuntimeError("OIDC transaction capacity reached")
            self._pending[transaction.state] = _PendingTransaction(
                transaction=transaction,
                browser_binding=browser_binding,
                expires_at=now + self._ttl_seconds,
            )
        return transaction

    def consume(
        self, *, state: str, browser_binding: str
    ) -> OIDCAuthorizationTransaction:
        """Accept a callback once, only from the initiating browser."""
        if not state or not browser_binding:
            raise ValueError("OIDC callback state and browser binding are required")
        with self._lock:
            now = self._clock()
            pending = self._pending.get(state)
            if pending is None:
                raise ValueError("unknown or replayed OIDC state")
            if now >= pending.expires_at:
                del self._pending[state]
                raise ValueError("expired OIDC state")
            if not hmac.compare_digest(pending.browser_binding, browser_binding):
                raise ValueError("OIDC browser binding mismatch")
            del self._pending[state]
            return pending.transaction

    def _prune(self, now: float) -> None:
        for state, pending in list(self._pending.items()):
            if now >= pending.expires_at:
                del self._pending[state]
