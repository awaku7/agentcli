from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.errors import MCPProtocolError
from uagent.tools.mcp.oauth_flow import (
    exchange_authorization_code,
    refresh_access_token,
)


def test_exchange_authorization_code_sends_pkce_form() -> None:
    async def scenario() -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["form"] = request.read().decode()
            return httpx.Response(
                200,
                json={
                    "access_token": "access-value",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": "refresh-value",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            token = await exchange_authorization_code(
                "https://auth.example/token",
                code="auth-code",
                code_verifier="v" * 64,
                client_id="uag-client",
                redirect_uri="http://127.0.0.1/callback",
                resource="https://mcp.example/mcp",
                http_client=client,
            )

        assert "grant_type=authorization_code" in captured["form"]
        assert "code_verifier=" in captured["form"]
        assert token.access_token == "access-value"
        assert token.refresh_token == "refresh-value"

    asyncio.run(scenario())


def test_refresh_token_exchange_and_invalid_response() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"token_type": "Bearer"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(MCPProtocolError) as exc_info:
                await refresh_access_token(
                    "https://auth.example/token",
                    refresh_token="refresh-value",
                    client_id="uag-client",
                    http_client=client,
                )
        assert exc_info.value.code == "MCP_OAUTH_TOKEN_FIELDS_MISSING"

    asyncio.run(scenario())
