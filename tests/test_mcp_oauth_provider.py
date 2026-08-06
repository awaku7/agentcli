from __future__ import annotations

import asyncio
from pathlib import Path


import httpx

from uagent.tools.mcp.oauth_provider import OAuthTokenProvider
from uagent.tools.mcp.stateless_transport import StatelessHTTPClient
from uagent.tools.mcp.token_store import StoredToken, TokenStore


def test_stateless_client_adds_auth_and_retries_after_401(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = TokenStore(
            tmp_path / "tokens.json",
            encrypt=lambda value: value[::-1],
            decrypt=lambda value: value[::-1],
        )
        store.save("issuer", "resource", StoredToken("old", "Bearer", refresh_token="r"))
        calls = 0

        async def header(force: bool) -> str:
            return "Bearer refreshed" if force else "Bearer old"

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                assert request.headers["Authorization"] == "Bearer old"
                return httpx.Response(401)
            assert request.headers["Authorization"] == "Bearer refreshed"
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = StatelessHTTPClient(
                "https://mcp.example/mcp",
                http_client=client,
                authorization_provider=header,
            )
            await transport.__aenter__()
            await transport.list_tools()
        assert calls == 2

    asyncio.run(scenario())


def test_oauth_provider_refreshes_and_preserves_rotating_token(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = TokenStore(
            tmp_path / "tokens.json",
            encrypt=lambda value: value[::-1],
            decrypt=lambda value: value[::-1],
        )
        store.save(
            "issuer",
            "resource",
            StoredToken("old", "Bearer", refresh_token="refresh-old"),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.content.decode().find("refresh-old") >= 0
            return httpx.Response(
                200,
                json={"access_token": "new", "token_type": "Bearer", "expires_in": 60},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OAuthTokenProvider(
                issuer="issuer",
                resource="resource",
                client_id="client",
                token_endpoint="https://auth.example/token",
                token_store=store,
                http_client=client,
            )
            assert await provider.authorization_header(True) == "Bearer new"
        assert store.load("issuer", "resource").refresh_token == "refresh-old"

    asyncio.run(scenario())


def test_oauth_provider_serializes_concurrent_refreshes(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = TokenStore(
            tmp_path / "tokens.json",
            encrypt=lambda value: value[::-1],
            decrypt=lambda value: value[::-1],
        )
        store.save(
            "issuer",
            "resource",
            StoredToken("old", "Bearer", refresh_token="refresh-old"),
        )
        refresh_calls = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal refresh_calls
            refresh_calls += 1
            await asyncio.sleep(0)
            return httpx.Response(
                200,
                json={"access_token": "new", "token_type": "Bearer", "expires_in": 60},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            provider = OAuthTokenProvider(
                issuer="issuer",
                resource="resource",
                client_id="client",
                token_endpoint="https://auth.example/token",
                token_store=store,
                http_client=client,
            )
            headers = await asyncio.gather(
                provider.authorization_header(True),
                provider.authorization_header(True),
            )
        assert headers == ["Bearer new", "Bearer new"]
        assert refresh_calls == 1

    asyncio.run(scenario())
