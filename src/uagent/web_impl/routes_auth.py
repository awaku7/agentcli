"""OIDC browser login and server-side session routes."""

from __future__ import annotations

from urllib.parse import urlencode
import secrets

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..auth.oidc_callback import complete_authorization_callback
from ..auth.oidc_sessions import get_oidc_session_store
from ..auth.oidc_transactions import OIDCTransactionStore
from ..auth.oidc_verifier import discover_provider
from ..env_utils import env_get
from ..runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
    create_identity_resolver,
    resolve_identity_mode,
)
from .app import app

OIDC_BINDING_COOKIE = "uag_oidc_binding"
OIDC_SESSION_COOKIE = "uag_oidc_session"
_OIDC_TRANSACTION_TTL = 300
_transactions = OIDCTransactionStore(ttl_seconds=_OIDC_TRANSACTION_TTL)


def _cookie_secure() -> bool:
    value = str(env_get("UAGENT_OIDC_COOKIE_SECURE", "1") or "").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _oidc_config() -> tuple[object, str, str, str]:
    if resolve_identity_mode() != "oidc":
        raise IdentityConfigurationError("OIDC identity mode is not enabled")
    issuer = str(env_get("UAGENT_OIDC_ISSUER", "") or "").strip()
    client_id = str(env_get("UAGENT_OIDC_CLIENT_ID", "") or "").strip()
    redirect_uri = str(env_get("UAGENT_OIDC_REDIRECT_URI", "") or "").strip()
    if not issuer or not client_id or not redirect_uri:
        raise IdentityConfigurationError("OIDC configuration is incomplete")
    return (
        discover_provider(issuer),
        client_id,
        redirect_uri,
        str(env_get("UAGENT_OIDC_CLIENT_SECRET", "") or ""),
    )


def _binding_cookie(request: Request) -> tuple[str, bool]:
    binding = str(request.cookies.get(OIDC_BINDING_COOKIE) or "").strip()
    if binding:
        return binding, False
    return secrets.token_urlsafe(32), True


def _set_binding_cookie(response: RedirectResponse, binding: str) -> None:
    response.set_cookie(
        OIDC_BINDING_COOKIE,
        binding,
        max_age=_OIDC_TRANSACTION_TTL,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


@app.get("/auth/oidc/login")
async def oidc_login(request: Request):
    """Start the browser-bound Authorization Code + PKCE flow."""
    try:
        metadata, client_id, redirect_uri, _ = _oidc_config()
        binding, is_new = _binding_cookie(request)
        transaction = _transactions.begin(binding)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "openid profile",
                "state": transaction.state,
                "nonce": transaction.nonce,
                "code_challenge": transaction.code_challenge,
                "code_challenge_method": "S256",
            }
        )
        response = RedirectResponse(
            f"{metadata.authorization_endpoint}?{query}", status_code=307
        )
        if is_new:
            _set_binding_cookie(response, binding)
        return response
    except (IdentityConfigurationError, IdentityResolutionError, RuntimeError) as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@app.get("/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
):
    """Consume a callback, verify the ID token, and issue an opaque session."""
    if error or not code or not state:
        return JSONResponse(
            status_code=400, content={"error": "OIDC authorization failed"}
        )
    binding = str(request.cookies.get(OIDC_BINDING_COOKIE) or "").strip()
    if not binding:
        return JSONResponse(
            status_code=400, content={"error": "OIDC browser binding missing"}
        )
    try:
        metadata, client_id, redirect_uri, client_secret = _oidc_config()
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            identity = await complete_authorization_callback(
                store=_transactions,
                metadata=metadata,
                state=state,
                browser_binding=binding,
                code=code,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                http_client=client,
            )
        session_token = get_oidc_session_store().create(identity)
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            OIDC_SESSION_COOKIE,
            session_token,
            max_age=int(env_get("UAGENT_OIDC_SESSION_TTL", "28800") or 28800),
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            path="/",
        )
        response.delete_cookie(OIDC_BINDING_COOKIE, path="/")
        return response
    except (IdentityConfigurationError, IdentityResolutionError, RuntimeError) as exc:
        return JSONResponse(status_code=401, content={"error": str(exc)})


@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Return the current principal without exposing token material."""
    try:
        identity = create_identity_resolver().resolve(request)
    except (IdentityConfigurationError, IdentityResolutionError):
        return JSONResponse(status_code=401, content={"authenticated": False})
    return {
        "authenticated": bool(identity.authenticated),
        "principal_id": identity.principal_id,
        "authn_kind": identity.authn_kind,
        "display_name": identity.display_name,
    }


@app.post("/auth/logout")
async def oidc_logout(request: Request):
    """Revoke the server-side session and clear the browser cookie."""
    token = str(request.cookies.get(OIDC_SESSION_COOKIE) or "").strip()
    get_oidc_session_store().revoke(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(OIDC_SESSION_COOKIE, path="/")
    response.delete_cookie(OIDC_BINDING_COOKIE, path="/")
    return response


__all__ = ["auth_status", "oidc_callback", "oidc_login", "oidc_logout"]
