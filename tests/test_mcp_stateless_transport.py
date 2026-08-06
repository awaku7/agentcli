from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.errors import MCPProtocolError
from uagent.tools.mcp.stateless_transport import StatelessHTTPClient


def test_stateless_list_tools_sends_protocol_headers() -> None:
    async def scenario() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.read()
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"tools": []},
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with StatelessHTTPClient(
                "https://example.test/mcp", http_client=http_client
            ) as client:
                result = await client.list_tools()

        headers = captured["headers"]
        assert isinstance(headers, dict)
        assert headers["mcp-protocol-version"] == "2026-07-28"
        assert headers["mcp-method"] == "tools/list"
        assert "mcp-name" not in headers
        assert result["result"] == {"tools": []}

    asyncio.run(scenario())


def test_stateless_call_tool_sends_tool_name_header_and_params() -> None:
    async def scenario() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = dict(request.headers)
            captured["body"] = request.read()
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"ok": True}},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with StatelessHTTPClient(
                "https://example.test", http_client=http_client
            ) as client:
                await client.call_tool("search", {"query": "MCP"})

        headers = captured["headers"]
        assert isinstance(headers, dict)
        assert headers["mcp-method"] == "tools/call"
        assert headers["mcp-name"] == "search"
        assert b'"name":"search"' in captured["body"]

    asyncio.run(scenario())


def test_stateless_jsonrpc_error_is_structured() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32601, "message": "method not found"},
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with StatelessHTTPClient(
                "https://example.test", http_client=http_client
            ) as client:
                with pytest.raises(MCPProtocolError) as exc_info:
                    await client.list_tools()

        assert exc_info.value.code == "MCP_JSONRPC_ERROR"
        assert exc_info.value.operation == "tools/list"

    asyncio.run(scenario())
