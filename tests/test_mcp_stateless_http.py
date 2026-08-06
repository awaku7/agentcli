from __future__ import annotations

import pytest

from uagent.tools.mcp.errors import MCPProtocolError
from uagent.tools.mcp.stateless_http import (
    build_protocol_headers,
    validate_protocol_headers,
)


def test_build_protocol_headers() -> None:
    headers = build_protocol_headers(
        method="tools/call",
        name="search",
        protocol_version="2026-07-28",
    )

    assert headers == {
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/call",
        "Mcp-Name": "search",
    }


def test_validate_protocol_headers_is_case_insensitive() -> None:
    validate_protocol_headers(
        {
            "mcp-protocol-version": "2026-07-28",
            "MCP-METHOD": "tools/list",
            "mcp-name": "catalog",
        },
        expected_method="tools/list",
        expected_name="catalog",
    )


def test_build_rejects_empty_method() -> None:
    with pytest.raises(MCPProtocolError) as exc_info:
        build_protocol_headers(method="")

    assert exc_info.value.code == "MCP_METHOD_MISSING"


def test_validate_rejects_method_mismatch() -> None:
    with pytest.raises(MCPProtocolError) as exc_info:
        validate_protocol_headers(
            {
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/list",
            },
            expected_method="tools/call",
        )

    assert exc_info.value.code == "MCP_METHOD_MISMATCH"
    assert exc_info.value.details["actual"] == "tools/list"


def test_validate_rejects_missing_protocol_version() -> None:
    with pytest.raises(MCPProtocolError) as exc_info:
        validate_protocol_headers(
            {"Mcp-Method": "tools/list"}, expected_method="tools/list"
        )

    assert exc_info.value.code == "MCP_PROTOCOL_VERSION_MISSING"
