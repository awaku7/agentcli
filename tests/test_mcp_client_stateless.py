from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.client import MCPClient
from uagent.tools.mcp.errors import MCPTransportError, MCPUnsupportedError


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


def test_mcp_client_auto_detects_stateless_http() -> None:
    async def scenario() -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if request.headers["mcp-method"] == "server/discover":
                result = {"supportedVersions": ["2025-11-25"]}
            else:
                assert request.headers["mcp-protocol-version"] == "2025-11-25"
                result = {"tools": []}
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": result},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with MCPClient(
                url="https://example.test",
                protocol_mode="auto",
                http_client=http_client,
            ) as client:
                assert client.protocol_info is not None
                assert client.protocol_info.mode.value == "stateless"
                assert client.protocol_info.detection_reason == "stateless_probe"
                await client.list_tools()

        assert calls == 2

    asyncio.run(scenario())


def test_mcp_client_auto_does_not_fallback_on_auth_error() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            with pytest.raises(MCPTransportError) as exc_info:
                async with MCPClient(
                    url="https://example.test",
                    protocol_mode="auto",
                    http_client=http_client,
                ):
                    pass
        assert exc_info.value.code == "MCP_HTTP_STATUS_ERROR"
        assert exc_info.value.details["status_code"] == 401

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


def test_mcp_stateless_request_sends_sse_accept_header() -> None:
    """Auto probe must advertise streamable-http compatible Accept header."""

    async def scenario() -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with MCPClient(
                url="https://example.test",
                protocol_mode="stateless",
                http_client=http_client,
            ) as client:
                await client.list_tools()

        assert requests
        accept = requests[0].headers.get("accept", "")
        assert "application/json" in accept
        assert "text/event-stream" in accept

    asyncio.run(scenario())


def test_mcp_auto_probe_406_is_not_treated_as_legacy_fallback() -> None:
    """A 406 probe response must be surfaced instead of triggering fallback."""

    async def scenario() -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = request.read()
            if b'"server/discover"' in body:
                calls.append("probe")
                return httpx.Response(406)
            calls.append("other")
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"tools": []}},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            with pytest.raises(MCPTransportError) as raised:
                async with MCPClient(
                    url="https://example.test",
                    protocol_mode="auto",
                    http_client=http_client,
                ) as client:
                    assert client is not None

            assert raised.value.code == "MCP_HTTP_STATUS_ERROR"
            assert raised.value.details.get("status_code") == 406

        assert calls and calls[0] == "probe"

    asyncio.run(scenario())
