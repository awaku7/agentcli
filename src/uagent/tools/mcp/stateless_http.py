"""Small, dependency-free helpers for MCP stateless HTTP requests.

The actual HTTP exchange remains in the adapter layer. These helpers keep
protocol header construction and validation deterministic and testable.
"""

from __future__ import annotations

from collections.abc import Mapping

from .errors import MCPProtocolError

DEFAULT_PROTOCOL_VERSION = "2026-07-28"


def build_protocol_headers(
    *,
    method: str,
    name: str | None = None,
    protocol_version: str = DEFAULT_PROTOCOL_VERSION,
) -> dict[str, str]:
    """Build required stateless MCP request headers."""
    method = method.strip()
    if not method:
        raise MCPProtocolError("MCP_METHOD_MISSING", "build_headers")
    if name is not None and not name.strip():
        raise MCPProtocolError("MCP_NAME_EMPTY", "build_headers")

    headers = {
        "MCP-Protocol-Version": protocol_version,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name.strip()
    return headers


def validate_protocol_headers(
    headers: Mapping[str, str],
    *,
    expected_method: str,
    expected_name: str | None = None,
) -> None:
    """Validate protocol headers before sending or routing a request."""
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    actual_method = normalized.get("mcp-method", "")
    if actual_method != expected_method:
        raise MCPProtocolError(
            "MCP_METHOD_MISMATCH",
            "validate_headers",
            {"expected": expected_method, "actual": actual_method},
        )

    if expected_name is not None:
        actual_name = normalized.get("mcp-name", "")
        if actual_name != expected_name:
            raise MCPProtocolError(
                "MCP_NAME_MISMATCH",
                "validate_headers",
                {"expected": expected_name, "actual": actual_name},
            )

    if not normalized.get("mcp-protocol-version"):
        raise MCPProtocolError(
            "MCP_PROTOCOL_VERSION_MISSING",
            "validate_headers",
        )
