"""Client ID Metadata Document (CIMD) retrieval and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .errors import MCPProtocolError, MCPTransportError


@dataclass(frozen=True)
class ClientMetadata:
    client_id: str
    redirect_uris: tuple[str, ...]
    grant_types: tuple[str, ...]
    response_types: tuple[str, ...]
    token_endpoint_auth_method: str
    raw: dict[str, Any]


def validate_client_id_url(client_id: str) -> str:
    """Validate the absolute HTTPS URL used as a CIMD client_id."""
    parsed = urlparse(client_id)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("CIMD client_id must be an absolute HTTPS URL")
    return client_id


def _json_response(response: Any) -> dict[str, Any]:
    if response.status_code >= 400:
        raise MCPTransportError(
            "MCP_CIMD_HTTP_ERROR",
            "oauth/client-metadata",
            {"status_code": response.status_code},
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise MCPProtocolError(
            "MCP_CIMD_INVALID_JSON", "oauth/client-metadata", {"error": str(exc)}
        ) from exc
    if not isinstance(payload, dict):
        raise MCPProtocolError(
            "MCP_CIMD_INVALID_DOCUMENT",
            "oauth/client-metadata",
            {"type": type(payload).__name__},
        )
    return payload


def parse_client_metadata(client_id: str, payload: dict[str, Any]) -> ClientMetadata:
    validate_client_id_url(client_id)
    actual_client_id = str(payload.get("client_id") or "")
    if actual_client_id != client_id:
        raise MCPProtocolError(
            "MCP_CIMD_CLIENT_ID_MISMATCH",
            "oauth/client-metadata",
            {"expected": client_id, "actual": actual_client_id},
        )
    redirect_uris = tuple(
        str(item) for item in payload.get("redirect_uris", []) if item
    )
    if not redirect_uris:
        raise MCPProtocolError(
            "MCP_CIMD_REDIRECT_URIS_MISSING", "oauth/client-metadata", {}
        )
    grant_types = tuple(str(item) for item in payload.get("grant_types", []) if item)
    response_types = tuple(
        str(item) for item in payload.get("response_types", []) if item
    )
    auth_method = str(payload.get("token_endpoint_auth_method") or "none")
    return ClientMetadata(
        client_id=actual_client_id,
        redirect_uris=redirect_uris,
        grant_types=grant_types,
        response_types=response_types,
        token_endpoint_auth_method=auth_method,
        raw=payload,
    )


async def fetch_client_metadata(client_id: str, *, http_client: Any) -> ClientMetadata:
    """Fetch and validate the CIMD document at ``client_id``."""
    validate_client_id_url(client_id)
    try:
        response = await http_client.get(
            client_id,
            headers={"Accept": "application/json"},
        )
    except Exception as exc:
        raise MCPTransportError(
            "MCP_CIMD_REQUEST_FAILED", "oauth/client-metadata", {"error": str(exc)}
        ) from exc
    return parse_client_metadata(client_id, _json_response(response))


__all__ = [
    "ClientMetadata",
    "fetch_client_metadata",
    "parse_client_metadata",
    "validate_client_id_url",
]
