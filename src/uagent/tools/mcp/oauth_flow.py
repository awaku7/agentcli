"""OAuth 2.1 authorization-code exchange for MCP.

This module performs network exchanges but deliberately does not persist or
log access tokens. Token storage and browser/UI integration remain caller
responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import MCPProtocolError, MCPTransportError


@dataclass(frozen=True)
class OAuthTokenResponse:
    access_token: str
    token_type: str
    expires_in: int | None
    refresh_token: str | None
    scope: str | None
    raw: dict[str, Any]


def _parse_token_response(response: Any) -> OAuthTokenResponse:
    if response.status_code >= 400:
        raise MCPTransportError(
            "MCP_OAUTH_TOKEN_HTTP_ERROR",
            "oauth/token",
            {"status_code": response.status_code},
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise MCPProtocolError(
            "MCP_OAUTH_INVALID_JSON", "oauth/token", {"error": str(exc)}
        ) from exc
    if not isinstance(payload, dict):
        raise MCPProtocolError(
            "MCP_OAUTH_INVALID_RESPONSE",
            "oauth/token",
            {"type": type(payload).__name__},
        )
    access_token = str(payload.get("access_token") or "")
    token_type = str(payload.get("token_type") or "")
    if not access_token or not token_type:
        raise MCPProtocolError("MCP_OAUTH_TOKEN_FIELDS_MISSING", "oauth/token", {})
    expires_raw = payload.get("expires_in")
    try:
        expires_in = int(expires_raw) if expires_raw is not None else None
    except (TypeError, ValueError):
        raise MCPProtocolError(
            "MCP_OAUTH_INVALID_EXPIRES_IN", "oauth/token", {}
        ) from None
    return OAuthTokenResponse(
        access_token=access_token,
        token_type=token_type,
        expires_in=expires_in,
        refresh_token=(
            str(payload["refresh_token"]) if payload.get("refresh_token") else None
        ),
        scope=(str(payload["scope"]) if payload.get("scope") else None),
        raw=payload,
    )


async def exchange_authorization_code(
    token_endpoint: str,
    *,
    code: str,
    code_verifier: str,
    client_id: str,
    redirect_uri: str,
    http_client: Any,
    resource: str | None = None,
) -> OAuthTokenResponse:
    """Exchange an authorization code using PKCE S256 verifier binding."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    if resource:
        data["resource"] = resource
    try:
        response = await http_client.post(
            token_endpoint,
            data=data,
            headers={"Accept": "application/json"},
        )
    except Exception as exc:
        raise MCPTransportError(
            "MCP_OAUTH_TOKEN_REQUEST_FAILED", "oauth/token", {"error": str(exc)}
        ) from exc
    return _parse_token_response(response)


async def refresh_access_token(
    token_endpoint: str,
    *,
    refresh_token: str,
    client_id: str,
    http_client: Any,
    resource: str | None = None,
) -> OAuthTokenResponse:
    """Refresh an access token without persisting the returned credentials."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if resource:
        data["resource"] = resource
    try:
        response = await http_client.post(
            token_endpoint,
            data=data,
            headers={"Accept": "application/json"},
        )
    except Exception as exc:
        raise MCPTransportError(
            "MCP_OAUTH_REFRESH_REQUEST_FAILED", "oauth/token", {"error": str(exc)}
        ) from exc
    return _parse_token_response(response)
