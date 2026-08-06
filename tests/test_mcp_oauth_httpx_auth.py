from __future__ import annotations

import asyncio

import httpx

from uagent.tools.mcp.oauth_provider import MCPOAuthHTTPXAuth


class _Provider:
    def __init__(self) -> None:
        self.refreshes = 0

    async def authorization_header(self, force_refresh: bool = False) -> str:
        if force_refresh:
            self.refreshes += 1
            return "Bearer new"
        return "Bearer old"


def test_httpx_auth_adds_bearer_and_retries_once() -> None:
    async def scenario() -> None:
        provider = _Provider()
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                assert request.headers["Authorization"] == "Bearer old"
                return httpx.Response(401)
            assert request.headers["Authorization"] == "Bearer new"
            return httpx.Response(200, json={"ok": True})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            auth=MCPOAuthHTTPXAuth(provider),
        ) as client:
            response = await client.get("https://mcp.example/mcp")
        assert response.status_code == 200
        assert calls == 2
        assert provider.refreshes == 1

    asyncio.run(scenario())
