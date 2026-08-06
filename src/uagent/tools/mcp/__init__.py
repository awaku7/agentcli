"""Internal MCP client abstractions.

This package contains protocol/client code shared by public MCP tools. It does
not produce localized user-facing messages; callers translate structured errors.
"""

from .client import MCPClient
from .protocol import MCPProtocolInfo, MCPProtocolMode, detect_protocol_mode

__all__ = [
    "MCPClient",
    "MCPProtocolInfo",
    "MCPProtocolMode",
    "detect_protocol_mode",
]
