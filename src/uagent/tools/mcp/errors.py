"""Structured errors for the internal MCP layer.

No localized user-facing messages belong here. Public tools translate these
stable error codes at their boundary.
"""

from __future__ import annotations

from typing import Any


class MCPError(RuntimeError):
    """Base error carrying a stable code and structured details."""

    def __init__(
        self,
        code: str,
        operation: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.operation = operation
        self.details = details or {}
        super().__init__(code)


class MCPProtocolError(MCPError):
    """Protocol negotiation or message-shape failure."""


class MCPTransportError(MCPError):
    """Transport, timeout, or connection failure."""


class MCPUnsupportedError(MCPError):
    """Requested MCP capability is not available."""
