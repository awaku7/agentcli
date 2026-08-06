from __future__ import annotations

import asyncio

import httpx
import pytest

from uagent.tools.mcp.oauth_cimd import fetch_client_metadata
from uagent.tools.mcp.oauth_metadata import fetch_authorization_server_metadata


def test_cimd_and_issuer_metadata_are_validated() -> None:
    async def scenario() -> None:
        client_id = "https://client.example/metadata.json"
        issuer = "https://auth.example"

        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == client_id:
                return httpx.Response(
                    200,
                    json={
                        "client_id": client_id,
                        "redirect_uris": ["http://127.0.0.1/callback"],
                        "grant_types": ["authorization_code"],
                        "response_types": ["code"],
                    },
                )
            if str(request.url) == issuer + "/.well-known/oauth-authorization-server":
                return httpx.Response(
                    200,
                    json={
                        "issuer": issuer,
                        "authorization_endpoint": issuer + "/authorize",
                        "token_endpoint": issuer + "/token",
                    },
                )
            return httpx.Response(404)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            metadata = await fetch_client_metadata(client_id, http_client=client)
            assert metadata.client_id == client_id
            authorization = await fetch_authorization_server_metadata(
                issuer, http_client=client
            )
            assert authorization.issuer == issuer

            with pytest.raises(ValueError, match="absolute HTTPS URL"):
                await fetch_client_metadata(
                    "http://client.example/metadata.json", http_client=client
                )

    asyncio.run(scenario())


def test_cimd_client_id_mismatch_is_rejected() -> None:
    async def scenario() -> None:
        requested = "https://client.example/metadata.json"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "client_id": "https://other.example/metadata.json",
                    "redirect_uris": ["http://127.0.0.1/callback"],
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(Exception, match="MCP_CIMD_CLIENT_ID_MISMATCH"):
                await fetch_client_metadata(requested, http_client=client)

    asyncio.run(scenario())
