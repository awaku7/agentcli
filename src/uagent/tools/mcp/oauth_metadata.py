"""MCP OAuth metadata discovery and validation.

This internal module has no localization and never stores tokens. It only
fetches metadata needed to construct an authorization flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from .errors import MCPProtocolError, MCPTransportError
from ...auth.oauth_common import OAuthMetadataTrustError, validate_endpoint_trust


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


def protected_resource_metadata_urls(resource_url: str) -> tuple[str, ...]:
    """Return path-aware then origin RFC 9728 discovery candidates."""
    parsed = urlparse(resource_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("resource URL must be absolute")
    path = parsed.path or "/"
    candidates: list[str] = []
    if path != "/":
        candidates.append(
            f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource{path}"
        )
    candidates.append(f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-protected-resource")
    return tuple(dict.fromkeys(candidates))


def authorization_server_metadata_urls(issuer: str) -> tuple[str, ...]:
    """Return RFC 8414 path-aware and origin discovery candidates."""
    parsed = urlparse(issuer)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("issuer must be an absolute URL")
    candidates: list[str] = []
    path = parsed.path.rstrip("/")
    if path:
        candidates.append(
            f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server{path}"
        )
    candidates.append(f"{parsed.scheme}://{parsed.netloc}/.well-known/oauth-authorization-server")
    return tuple(dict.fromkeys(candidates))


def _is_localhost(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"}


def validate_oauth_transport(url: str, *, allow_http_localhost: bool = True) -> None:
    """Reject insecure OAuth metadata and endpoint URLs by default."""
    parsed = urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and allow_http_localhost and _is_localhost(parsed.hostname or ""):
        return
    raise MCPProtocolError("MCP_INSECURE_OAUTH_URL", "oauth-metadata", {"url": url})


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
    payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    for url in protected_resource_metadata_urls(resource_url):
        try:
            response = await http_client.get(url, headers={"Accept": "application/json"})
            if response.status_code >= 400:
                continue
            candidate = _json_response(response, "oauth-protected-resource")
            resource = str(candidate.get("resource") or "")
            if resource and resource != resource_url:
                last_error = MCPProtocolError(
                    "MCP_RESOURCE_METADATA_MISMATCH",
                    "oauth-protected-resource",
                    {"expected": resource_url, "actual": resource},
                )
                continue
            if "authorization_servers" not in candidate:
                continue
            payload = candidate
            break
        except Exception as exc:
            last_error = exc
    if payload is None:
        if last_error is not None:
            raise last_error
        raise MCPTransportError(
            "MCP_METADATA_REQUEST_FAILED",
            "oauth-protected-resource",
            {"error": "no valid metadata candidate"},
        )
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
    payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    for url in authorization_server_metadata_urls(issuer):
        try:
            response = await http_client.get(url, headers={"Accept": "application/json"})
            if response.status_code >= 400:
                continue
            candidate = _json_response(response, "oauth-authorization-server")
            actual_issuer = str(candidate.get("issuer") or "")
            if actual_issuer.rstrip("/") != issuer.rstrip("/"):
                last_error = MCPProtocolError(
                    "MCP_ISSUER_MISMATCH",
                    "oauth-authorization-server",
                    {"expected": issuer, "actual": actual_issuer},
                )
                continue
            payload = candidate
            break
        except Exception as exc:
            last_error = exc
    if payload is None:
        if last_error is not None:
            raise last_error
        raise MCPTransportError(
            "MCP_METADATA_REQUEST_FAILED",
            "oauth-authorization-server",
            {"error": "no valid metadata candidate"},
        )
    actual_issuer = str(payload.get("issuer") or "")
    authorization_endpoint = str(payload.get("authorization_endpoint") or "")
    token_endpoint = str(payload.get("token_endpoint") or "")
    if not authorization_endpoint or not token_endpoint:
        raise MCPProtocolError(
            "MCP_AUTHORIZATION_ENDPOINT_MISSING", "oauth-authorization-server", {}
        )
    registration_endpoint = payload.get("registration_endpoint")
    try:
        authorization_endpoint = validate_endpoint_trust(authorization_endpoint, issuer)
        token_endpoint = validate_endpoint_trust(token_endpoint, issuer)
        if registration_endpoint := payload.get("registration_endpoint"):
            registration_endpoint = validate_endpoint_trust(str(registration_endpoint), issuer)
    except OAuthMetadataTrustError as exc:
        raise MCPProtocolError(
            "MCP_OAUTH_ENDPOINT_TRUST_FAILURE",
            "oauth-authorization-server",
            {"error": str(exc)},
        ) from exc
    scopes = tuple(str(item) for item in payload.get("scopes_supported", []) if item)
    return AuthorizationServerMetadata(
        actual_issuer,
        authorization_endpoint,
        token_endpoint,
        str(registration_endpoint) if registration_endpoint else None,
        scopes,
        payload,
    )
