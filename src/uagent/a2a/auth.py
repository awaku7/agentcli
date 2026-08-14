from __future__ import annotations

from typing import Optional

try:
    from fastapi import Header, Request
except ImportError:
    from .._pip_auto import install_with_status as _install_fa

    _install_fa("fastapi")
    from fastapi import Header, Request

from ..auth import CredentialKind, resolve_credential_secret
from ..i18n import _
from .errors import A2AHttpError


def _norm(v: str) -> str:
    return (v or "").strip()


def require_bearer_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Bearer auth for A2A endpoints.

    Token source:
      - UAGENT_A2A_TOKEN (required for authenticated endpoints)

    If UAGENT_A2A_TOKEN is empty, authenticated endpoints are disabled.
    """

    store = getattr(request.app.state, "credential_store", None)
    expected = _norm(
        resolve_credential_secret(
            "a2a/default",
            kind=CredentialKind.A2A,
            store=store,
            env_names=("UAGENT_A2A_TOKEN",),
        )
        or ""
    )
    if not expected:
        raise A2AHttpError(
            status_code=503,
            code="UNAVAILABLE",
            message=_(
                "A2A authentication is not configured (UAGENT_A2A_TOKEN is empty)."
            ),
        )

    auth = _norm(authorization or "")
    prefix = "bearer "
    if not auth.lower().startswith(prefix):
        raise A2AHttpError(
            status_code=401,
            code="UNAUTHENTICATED",
            message=_(
                "Missing or invalid Authorization header (expected: Bearer <token>)."
            ),
        )

    got = auth[len(prefix) :].strip()
    if got != expected:
        raise A2AHttpError(
            status_code=403,
            code="PERMISSION_DENIED",
            message=_("Invalid bearer token."),
        )
