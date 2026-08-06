from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.errors import MCPUnsupportedError


def test_mcp_client_stateless_routes_list_and_call_without_session() -> None:
    async def scenario() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            body = request.read()
            if b'"tools/list"' in body:
                result = {"tools": [{"name": "search"}]}
            else:
                result = {"content": [{"type": "text", "text": "ok"}]}
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": result},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with MCPClient(
                url="https://example.test",
                protocol_mode="stateless",
                http_client=http_client,
            ) as client:
                tools = await client.list_tools()
                result = await client.call_tool("search", {"query": "MCP"})
                assert client.session is None
                assert client.protocol_info is not None
                assert client.protocol_info.mode.value == "stateless"

        assert tools["result"]["tools"][0]["name"] == "search"
        assert result["result"]["content"][0]["text"] == "ok"
        assert len(requests) == 2
        assert requests[0].headers["mcp-method"] == "tools/list"
        assert requests[1].headers["mcp-method"] == "tools/call"
        assert requests[1].headers["mcp-name"] == "search"

    asyncio.run(scenario())


def test_mcp_client_rejects_stateless_stdio() -> None:
    async def scenario() -> None:
        with pytest.raises(MCPUnsupportedError) as exc_info:
            async with MCPClient(
                command="example-server",
                protocol_mode="stateless",
            ):
                pass
        assert exc_info.value.code == "MCP_STATELESS_HTTP_REQUIRED"

    asyncio.run(scenario())
