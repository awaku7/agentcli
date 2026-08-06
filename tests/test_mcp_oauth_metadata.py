from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.errors import MCPProtocolError
from uagent.tools.mcp.oauth_metadata import (
    fetch_authorization_server_metadata,
    fetch_protected_resource_metadata,
)


def test_fetches_and_validates_oauth_metadata() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("oauth-protected-resource"):
                return httpx.Response(
                    200,
                    json={
                        "resource": "https://mcp.example/mcp",
                        "authorization_servers": ["https://auth.example"],
                        "scopes_supported": ["mcp:read"],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "issuer": "https://auth.example",
                    "authorization_endpoint": "https://auth.example/authorize",
                    "token_endpoint": "https://auth.example/token",
                    "scopes_supported": ["mcp:read"],
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            resource = await fetch_protected_resource_metadata(
                "https://mcp.example/mcp", http_client=client
            )
            auth = await fetch_authorization_server_metadata(
                resource.authorization_servers[0], http_client=client
            )

        assert resource.scopes_supported == ("mcp:read",)
        assert auth.token_endpoint.endswith("/token")

    asyncio.run(scenario())


def test_rejects_issuer_mismatch() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "issuer": "https://evil.example",
                    "authorization_endpoint": "https://evil.example/authorize",
                    "token_endpoint": "https://evil.example/token",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(MCPProtocolError) as exc_info:
                await fetch_authorization_server_metadata(
                    "https://auth.example", http_client=client
                )
        assert exc_info.value.code == "MCP_ISSUER_MISMATCH"

    asyncio.run(scenario())
