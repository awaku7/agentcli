"""Turn-local identity contracts for Memory V3.

This module deliberately contains no provider-specific authentication logic.  It
normalizes an already selected identity mode into immutable identity/turn
contexts and provides ContextVar helpers for legacy call paths. Web connections
bind their authenticated identity before creating turn contexts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
from typing import Any, Callable, Iterator, TypeVar

from ..env_utils import env_get

KNOWN_IDENTITY_MODES = (
    "local",
    "oidc",
    "oauth",
    "trusted_proxy",
    "windows_ad",
    "token",
    "external",
)


class IdentityConfigurationError(RuntimeError):
    """Raised when the configured identity mode cannot be selected safely."""


class IdentityResolutionError(RuntimeError):
    """Raised when an identity resolver cannot produce a valid principal."""


@dataclass(frozen=True)
class IdentityContext:
    """Authenticated principal metadata normalized for UAG runtime use."""

    principal_id: str
    authenticated: bool
    authn_kind: str
    issuer: str = ""
    subject: str = ""
    display_name: str = ""

    def __post_init__(self) -> None:
        principal_id = str(self.principal_id or "").strip()
        authn_kind = str(self.authn_kind or "").strip().lower()
        if not principal_id:
            raise IdentityResolutionError("principal_id is required")
        if not authn_kind:
            raise IdentityResolutionError("authn_kind is required")
        object.__setattr__(self, "principal_id", principal_id)
        object.__setattr__(self, "authn_kind", authn_kind)
        object.__setattr__(self, "issuer", str(self.issuer or "").strip())
        object.__setattr__(self, "subject", str(self.subject or "").strip())
        object.__setattr__(self, "display_name", str(self.display_name or "").strip())


@dataclass(frozen=True)
class TurnContext:
    """Immutable actor/workspace/session boundary for one user turn."""

    principal_id: str
    room_id: str
    project_id: str
    session_id: str
    entry_point: str
    authenticated: bool
    authn_kind: str

    def __post_init__(self) -> None:
        principal_id = str(self.principal_id or "").strip()
        entry_point = str(self.entry_point or "").strip().lower()
        authn_kind = str(self.authn_kind or "").strip().lower()
        if not principal_id:
            raise IdentityResolutionError("turn principal_id is required")
        if not entry_point:
            raise IdentityResolutionError("turn entry_point is required")
        if not authn_kind:
            raise IdentityResolutionError("turn authn_kind is required")
        object.__setattr__(self, "principal_id", principal_id)
        object.__setattr__(self, "room_id", str(self.room_id or "").strip())
        object.__setattr__(self, "project_id", str(self.project_id or "").strip())
        object.__setattr__(self, "session_id", str(self.session_id or "").strip())
        object.__setattr__(self, "entry_point", entry_point)
        object.__setattr__(self, "authn_kind", authn_kind)

    @classmethod
    def from_identity(
        cls,
        identity: IdentityContext,
        *,
        room_id: str = "",
        project_id: str = "",
        session_id: str = "",
        entry_point: str,
    ) -> "TurnContext":
        return cls(
            principal_id=identity.principal_id,
            room_id=room_id,
            project_id=project_id,
            session_id=session_id,
            entry_point=entry_point,
            authenticated=identity.authenticated,
            authn_kind=identity.authn_kind,
        )


class IdentityResolver(ABC):
    """Authentication-provider-neutral principal resolver interface."""

    mode: str = ""

    @abstractmethod
    def resolve(self, request_context: Any = None) -> IdentityContext:
        """Resolve one trusted request context into a stable principal."""
        raise NotImplementedError


class LocalIdentityResolver(IdentityResolver):
    """Single-user/local resolver used by CLI, GUI, and local deployments."""

    mode = "local"

    def resolve(self, request_context: Any = None) -> IdentityContext:
        del request_context
        return IdentityContext(
            principal_id="local",
            authenticated=True,
            authn_kind="local",
        )


class OIDCIdentityResolver(IdentityResolver):
    """Resolve a Web request from the server-side OIDC session cookie."""

    mode = "oidc"
    cookie_name = "uag_oidc_session"

    def resolve(self, request_context: Any = None) -> IdentityContext:
        cookies = getattr(request_context, "cookies", None)
        token = str((cookies or {}).get(self.cookie_name) or "").strip()
        if not token:
            raise IdentityResolutionError("OIDC session cookie is missing")
        from ..auth.oidc_sessions import get_oidc_session_store

        identity = get_oidc_session_store().resolve(token)
        if identity is None:
            raise IdentityResolutionError("OIDC session is invalid or expired")
        return identity


def resolve_identity_mode(mode: str | None = None) -> str:
    """Return one explicitly selected identity mode without silent fallback."""
    raw = mode if mode is not None else env_get("UAGENT_IDENTITY_MODE", "local")
    selected = str(raw or "local").strip().lower()
    if selected not in KNOWN_IDENTITY_MODES:
        raise IdentityConfigurationError(f"unsupported identity mode: {selected}")
    return selected


def create_identity_resolver(mode: str | None = None) -> IdentityResolver:
    """Create the configured resolver without implicit local fallback.

    ``local`` resolves the process-local principal. ``oidc`` resolves a
    server-side browser session cookie. Enterprise modes delegate credential
    validation to their selected adapter without fallback.
    """
    selected = resolve_identity_mode(mode)
    if selected == "local":
        return LocalIdentityResolver()
    if selected == "oidc":
        return OIDCIdentityResolver()
    from .enterprise_identity import enterprise_resolver

    return enterprise_resolver(selected)


def resolve_turn_context(
    *,
    entry_point: str,
    room_id: str = "",
    project_id: str = "",
    session_id: str = "",
    request_context: Any = None,
    resolver: IdentityResolver | None = None,
    mode: str | None = None,
) -> tuple[IdentityContext, TurnContext]:
    """Resolve identity and create the immutable context for one turn."""
    if resolver is not None and mode is not None:
        raise ValueError("resolver and mode are mutually exclusive")
    active_resolver = resolver or create_identity_resolver(mode)
    identity = active_resolver.resolve(request_context)
    turn = TurnContext.from_identity(
        identity,
        room_id=room_id,
        project_id=project_id,
        session_id=session_id,
        entry_point=entry_point,
    )
    return identity, turn


_CURRENT_IDENTITY: ContextVar[IdentityContext | None] = ContextVar(
    "uagent_identity_context", default=None
)
_CURRENT_TURN: ContextVar[TurnContext | None] = ContextVar(
    "uagent_turn_context", default=None
)


def get_current_identity_context() -> IdentityContext | None:
    """Return the identity bound to the current execution context."""
    return _CURRENT_IDENTITY.get()


def get_current_turn_context() -> TurnContext | None:
    """Return the turn bound to the current execution context."""
    return _CURRENT_TURN.get()


@contextmanager
def bind_turn_context(
    turn_context: TurnContext,
    *,
    identity_context: IdentityContext | None = None,
) -> Iterator[TurnContext]:
    """Bind identity/turn data for the duration of one execution scope."""
    identity = identity_context or get_current_identity_context()
    if identity is None:
        identity = IdentityContext(
            principal_id=turn_context.principal_id,
            authenticated=turn_context.authenticated,
            authn_kind=turn_context.authn_kind,
        )
    if identity.principal_id != turn_context.principal_id:
        raise IdentityResolutionError("identity/turn principal mismatch")
    if identity.authenticated != turn_context.authenticated:
        raise IdentityResolutionError("identity/turn authentication mismatch")
    if identity.authn_kind != turn_context.authn_kind:
        raise IdentityResolutionError("identity/turn authn_kind mismatch")

    identity_token = _CURRENT_IDENTITY.set(identity)
    turn_token = _CURRENT_TURN.set(turn_context)
    try:
        yield turn_context
    finally:
        _CURRENT_TURN.reset(turn_token)
        _CURRENT_IDENTITY.reset(identity_token)


_T = TypeVar("_T")


def call_with_turn_context(
    turn_context: TurnContext,
    fn: Callable[..., _T],
    *args: Any,
    identity_context: IdentityContext | None = None,
    **kwargs: Any,
) -> _T:
    """Call ``fn`` with a turn-local ContextVar binding."""
    with bind_turn_context(turn_context, identity_context=identity_context):
        return fn(*args, **kwargs)


def submit_with_current_context(
    executor: Any,
    fn: Callable[..., _T],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Submit work while explicitly propagating all current ContextVars."""
    context = copy_context()
    return executor.submit(context.run, fn, *args, **kwargs)


__all__ = [
    "KNOWN_IDENTITY_MODES",
    "IdentityConfigurationError",
    "IdentityContext",
    "IdentityResolutionError",
    "IdentityResolver",
    "LocalIdentityResolver",
    "OIDCIdentityResolver",
    "TurnContext",
    "bind_turn_context",
    "call_with_turn_context",
    "create_identity_resolver",
    "get_current_identity_context",
    "get_current_turn_context",
    "resolve_identity_mode",
    "resolve_turn_context",
    "submit_with_current_context",
]
