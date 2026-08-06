from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from uagent.tools.mcp.oauth_browser_flow import authorize_with_local_callback
from uagent.tools.mcp.oauth_metadata import AuthorizationServerMetadata
from uagent.tools.mcp.token_store import TokenStore


def test_local_browser_flow_opens_url_and_stores_token(tmp_path: Path) -> None:
    async def scenario() -> None:
        metadata = AuthorizationServerMetadata(
            issuer="https://auth.example",
            authorization_endpoint="https://auth.example/authorize",
            token_endpoint="https://auth.example/token",
            registration_endpoint=None,
            scopes_supported=("mcp:read",),
            raw={},
        )
        store = TokenStore(
            tmp_path / "tokens.json",
            encrypt=lambda value: value[::-1],
            decrypt=lambda value: value[::-1],
        )
        opened: list[str] = []

        def opener(url: str) -> None:
            opened.append(url)
            query = parse_qs(urlsplit(url).query)
            redirect = query["redirect_uri"][0]
            state = query["state"][0]

            async def redirect_request() -> None:
                target = urlsplit(redirect)
                reader, writer = await asyncio.open_connection(target.hostname, target.port)
                writer.write(
                    f"GET {target.path}?code=code-1&state={state} HTTP/1.1\r\n"
                    "Host: localhost\r\n\r\n".encode()
                )
                await writer.drain()
                await reader.read(1024)
                writer.close()
                await writer.wait_closed()

            asyncio.create_task(redirect_request())

        def token_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "token_type": "Bearer",
                    "refresh_token": "refresh-1",
                    "expires_in": 300,
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(token_handler)
        ) as client:
            token = await authorize_with_local_callback(
                metadata=metadata,
                issuer=metadata.issuer,
                resource="https://mcp.example/mcp",
                client_id="uag",
                scope="mcp:read",
                token_store=store,
                http_client=client,
                browser_opener=opener,
                timeout=2,
            )
        assert opened and "code_challenge_method=S256" in opened[0]
        assert token.access_token == "access-1"
        assert store.load(metadata.issuer, "https://mcp.example/mcp").refresh_token == "refresh-1"

    asyncio.run(scenario())
