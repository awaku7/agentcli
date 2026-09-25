from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Optional

try:
    from fastapi import Header, Request
except ImportError:
    from .._pip_auto import install_with_status as _install_fa

    _install_fa("fastapi")
    from fastapi import Header, Request

from ..auth import CredentialKind, resolve_credential_secret
from ..i18n import _
from ..runtime.observability.bootstrap import get_observability_backend
from .errors import A2AHttpError


def _norm(v: str) -> str:
    return (v or "").strip()


async def require_bearer_auth(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> AsyncIterator[dict[str, str]]:
    """Bearer auth for A2A endpoints and trusted trace-context boundary.

    Token source:
      - UAGENT_A2A_TOKEN (required for authenticated endpoints)

    If UAGENT_A2A_TOKEN is empty, authenticated endpoints are disabled.
    Credential lookup stays off the request event loop. W3C trace context is
    considered only after bearer authentication succeeds and never supplies
    identity or authorization.
    """

    store = getattr(request.app.state, "credential_store", None)
    expected_secret = await asyncio.to_thread(
        resolve_credential_secret,
        "a2a/default",
        kind=CredentialKind.A2A,
        store=store,
        env_names=("UAGENT_A2A_TOKEN",),
    )
    expected = _norm(expected_secret or "")
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

    carrier: dict[str, str] = {}
    traceparent = _norm(request.headers.get("traceparent", ""))
    tracestate = _norm(request.headers.get("tracestate", ""))
    if traceparent:
        carrier["traceparent"] = traceparent
    if tracestate:
        carrier["tracestate"] = tracestate

    backend = get_observability_backend()
    try:
        manager = backend.attach_remote_context(carrier)
    except Exception:
        yield carrier
        return

    with manager:
        yield carrier
