from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.errors import MCPProtocolError
from uagent.tools.mcp.oauth_cimd import fetch_client_metadata, parse_client_metadata


CLIENT_ID = "https://client.example/metadata.json"


def test_parse_cimd_validates_client_id_and_redirects() -> None:
    metadata = parse_client_metadata(
        CLIENT_ID,
        {
            "client_id": CLIENT_ID,
            "redirect_uris": ["http://127.0.0.1/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert metadata.client_id == CLIENT_ID
    assert metadata.redirect_uris == ("http://127.0.0.1/callback",)
    assert metadata.token_endpoint_auth_method == "none"


def test_parse_cimd_rejects_mismatched_client_id() -> None:
    with pytest.raises(MCPProtocolError) as error:
        parse_client_metadata(CLIENT_ID, {"client_id": "https://other.example/id"})
    assert error.value.code == "MCP_CIMD_CLIENT_ID_MISMATCH"


def test_fetch_cimd_uses_client_id_url() -> None:
    async def scenario() -> None:
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "client_id": CLIENT_ID,
                    "redirect_uris": ["http://127.0.0.1/callback"],
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            metadata = await fetch_client_metadata(CLIENT_ID, http_client=client)
        assert metadata.client_id == CLIENT_ID
        assert requested == [CLIENT_ID]

    asyncio.run(scenario())
