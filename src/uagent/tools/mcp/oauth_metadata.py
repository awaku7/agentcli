"""MCP OAuth metadata discovery and validation.

This internal module has no localization and never stores tokens. It only
fetches metadata needed to construct an authorization flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from .errors import MCPProtocolError, MCPTransportError


@dataclass(frozen=True)
class ProtectedResourceMetadata:
    resource: str
    authorization_servers: tuple[str, ...]
    scopes_supported: tuple[str, ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class AuthorizationServerMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None
    scopes_supported: tuple[str, ...]
    raw: dict[str, Any]


def protected_resource_metadata_url(resource_url: str) -> str:
    """Return the RFC 9728 metadata URL for an MCP resource server."""
    parsed = urlparse(resource_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("resource URL must be absolute")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(origin + "/", ".well-known/oauth-protected-resource")


def authorization_server_metadata_url(issuer: str) -> str:
    """Return the RFC 8414 metadata URL for an authorization server."""
    parsed = urlparse(issuer)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("issuer must be an absolute URL")
    return urljoin(issuer.rstrip("/") + "/", ".well-known/oauth-authorization-server")


def _json_response(response: Any, operation: str) -> dict[str, Any]:
    if response.status_code >= 400:
        raise MCPTransportError(
            "MCP_HTTP_STATUS_ERROR", operation, {"status_code": response.status_code}
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise MCPProtocolError(
            "MCP_INVALID_JSON_RESPONSE", operation, {"error": str(exc)}
        ) from exc
    if not isinstance(payload, dict):
        raise MCPProtocolError(
            "MCP_INVALID_RESPONSE_OBJECT", operation, {"type": type(payload).__name__}
        )
    return payload


async def fetch_protected_resource_metadata(
    resource_url: str,
    *,
    http_client: Any,
) -> ProtectedResourceMetadata:
    url = protected_resource_metadata_url(resource_url)
    try:
        response = await http_client.get(url, headers={"Accept": "application/json"})
    except Exception as exc:
        raise MCPTransportError(
            "MCP_METADATA_REQUEST_FAILED",
            "oauth-protected-resource",
            {"error": str(exc)},
        ) from exc
    payload = _json_response(response, "oauth-protected-resource")
    resource = str(payload.get("resource") or resource_url)
    if resource != resource_url:
        raise MCPProtocolError(
            "MCP_RESOURCE_METADATA_MISMATCH",
            "oauth-protected-resource",
            {"expected": resource_url, "actual": resource},
        )
    servers = tuple(
        str(item) for item in payload.get("authorization_servers", []) if item
    )
    if not servers:
        raise MCPProtocolError(
            "MCP_AUTHORIZATION_SERVER_MISSING", "oauth-protected-resource", {}
        )
    scopes = tuple(str(item) for item in payload.get("scopes_supported", []) if item)
    return ProtectedResourceMetadata(resource, servers, scopes, payload)


async def fetch_authorization_server_metadata(
    issuer: str,
    *,
    http_client: Any,
) -> AuthorizationServerMetadata:
    url = authorization_server_metadata_url(issuer)
    try:
        response = await http_client.get(url, headers={"Accept": "application/json"})
    except Exception as exc:
        raise MCPTransportError(
            "MCP_METADATA_REQUEST_FAILED",
            "oauth-authorization-server",
            {"error": str(exc)},
        ) from exc
    payload = _json_response(response, "oauth-authorization-server")
    actual_issuer = str(payload.get("issuer") or "")
    if actual_issuer.rstrip("/") != issuer.rstrip("/"):
        raise MCPProtocolError(
            "MCP_ISSUER_MISMATCH",
            "oauth-authorization-server",
            {"expected": issuer, "actual": actual_issuer},
        )
    authorization_endpoint = str(payload.get("authorization_endpoint") or "")
    token_endpoint = str(payload.get("token_endpoint") or "")
    if not authorization_endpoint or not token_endpoint:
        raise MCPProtocolError(
            "MCP_AUTHORIZATION_ENDPOINT_MISSING", "oauth-authorization-server", {}
        )
    registration_endpoint = payload.get("registration_endpoint")
    scopes = tuple(str(item) for item in payload.get("scopes_supported", []) if item)
    return AuthorizationServerMetadata(
        actual_issuer,
        authorization_endpoint,
        token_endpoint,
        str(registration_endpoint) if registration_endpoint else None,
        scopes,
        payload,
    )
