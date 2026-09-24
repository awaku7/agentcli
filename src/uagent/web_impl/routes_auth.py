"""OIDC browser login and server-side session routes."""

from __future__ import annotations

import re
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from ..auth.oidc_callback import complete_authorization_callback
from ..auth.oidc_sessions import get_oidc_session_store
from ..auth.oidc_transactions import OIDCTransactionStore
from ..auth.oidc_verifier import discover_provider
from ..env_utils import env_get
from ..runtime.auth_management import (
    authentication_configuration_fingerprint,
    positive_integer_setting,
    validate_authentication_configuration,
)
from ..runtime.identity_context import (
    IdentityConfigurationError,
    IdentityResolutionError,
    create_identity_resolver,
    resolve_identity_mode,
)
from ..runtime.room_access import configured_admin_principals
from .app import app

OIDC_BINDING_COOKIE = "uag_oidc_binding"
OIDC_SESSION_COOKIE = "uag_oidc_session"
_OIDC_TRANSACTION_TTL = 300
_transactions = OIDCTransactionStore(ttl_seconds=_OIDC_TRANSACTION_TTL)


def _cookie_secure() -> bool:
    value = str(env_get("UAGENT_OIDC_COOKIE_SECURE", "1") or "").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _oidc_scopes() -> str:
    raw = str(env_get("UAGENT_OIDC_GRAPH_SCOPE", "") or "").strip()
    extra = raw.split()
    if any(not re.fullmatch(r"[A-Za-z0-9._:/-]+", scope) for scope in extra):
        raise IdentityConfigurationError(
            "UAGENT_OIDC_GRAPH_SCOPE contains an invalid scope"
        )
    if len(extra) != len(set(extra)):
        raise IdentityConfigurationError(
            "UAGENT_OIDC_GRAPH_SCOPE contains duplicate scopes"
        )
    return " ".join(dict.fromkeys(("openid", "profile", *extra)))


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
                "scope": _oidc_scopes(),
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
        configuration_fingerprint = authentication_configuration_fingerprint()
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
        session_token = get_oidc_session_store().create(
            identity,
            expected_configuration_fingerprint=configuration_fingerprint,
        )
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            OIDC_SESSION_COOKIE,
            session_token,
            max_age=positive_integer_setting("UAGENT_OIDC_SESSION_TTL", 28800),
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
    """Return safe mode health and current sign-in state without secret material."""
    report = validate_authentication_configuration().public_dict()
    try:
        identity = create_identity_resolver().resolve(request)
    except (IdentityConfigurationError, IdentityResolutionError):
        return {**report, "authenticated": False}
    return {
        **report,
        "authenticated": bool(identity.authenticated),
        "authn_kind": identity.authn_kind,
        "display_name": identity.display_name,
    }


@app.get("/api/admin/auth/status")
async def admin_auth_status(request: Request):
    """Return operational authentication health to configured administrators."""
    try:
        identity = create_identity_resolver().resolve(request)
    except (IdentityConfigurationError, IdentityResolutionError):
        return JSONResponse(
            status_code=401, content={"error": "authentication required"}
        )
    if identity.principal_id not in configured_admin_principals():
        return JSONResponse(
            status_code=403, content={"error": "administrator required"}
        )
    return {
        **validate_authentication_configuration().public_dict(),
        "active_oidc_sessions": get_oidc_session_store().active_count(),
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


__all__ = [
    "admin_auth_status",
    "auth_status",
    "oidc_callback",
    "oidc_login",
    "oidc_logout",
]
