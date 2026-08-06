"""Internal MCP client abstractions.

This package contains protocol/client code shared by public MCP tools. It does
not produce localized user-facing messages; callers translate structured errors.
"""

from .protocol import MCPProtocolMode, MCPProtocolInfo, detect_protocol_mode

__all__ = ["MCPProtocolInfo", "MCPProtocolMode", "detect_protocol_mode"]
