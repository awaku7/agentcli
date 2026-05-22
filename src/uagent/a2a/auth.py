from __future__ import annotations

from typing import Optional

from fastapi import Header

from ..env_utils import env_get
from .errors import A2AHttpError


def _norm(v: str) -> str:
    return (v or "").strip()


def require_bearer_auth(authorization: Optional[str] = Header(default=None)) -> None:
    """Bearer auth for A2A endpoints.

    Token source:
      - UAGENT_A2A_TOKEN (required for authenticated endpoints)

    If UAGENT_A2A_TOKEN is empty, authenticated endpoints are disabled.
    """

    expected = _norm(env_get("UAGENT_A2A_TOKEN", ""))
    if not expected:
        raise A2AHttpError(
            status_code=503,
            code="UNAVAILABLE",
            message="A2A authentication is not configured (UAGENT_A2A_TOKEN is empty).",
        )

    auth = _norm(authorization or "")
    prefix = "bearer "
    if not auth.lower().startswith(prefix):
        raise A2AHttpError(
            status_code=401,
            code="UNAUTHENTICATED",
            message="Missing or invalid Authorization header (expected: Bearer <token>).",
        )

    got = auth[len(prefix) :].strip()
    if got != expected:
        raise A2AHttpError(
            status_code=403,
            code="PERMISSION_DENIED",
            message="Invalid bearer token.",
        )
