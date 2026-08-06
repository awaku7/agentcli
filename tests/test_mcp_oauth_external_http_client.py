from __future__ import annotations

import httpx
import pytest

from uagent.tools.mcp.oauth_provider import (
    MCPOAuthHTTPXAuth,
    OAuthTokenProvider,
    attach_oauth_httpx_auth,
)


def _provider() -> OAuthTokenProvider:
    return OAuthTokenProvider(
        issuer="issuer",
        resource="resource",
        client_id="client",
        token_endpoint="https://auth.example/token",
        token_store=None,  # type: ignore[arg-type]
        http_client=None,
    )


def test_external_http_client_receives_oauth_auth() -> None:
    client = httpx.AsyncClient()
    try:
        result = attach_oauth_httpx_auth(client, _provider())
        assert result is client
        assert isinstance(client.auth, MCPOAuthHTTPXAuth)
    finally:
        import asyncio

        asyncio.run(client.aclose())


def test_external_conflicting_auth_is_not_overwritten() -> None:
    client = httpx.AsyncClient(auth=httpx.BasicAuth("user", "password"))
    try:
        with pytest.raises(ValueError, match="conflicting auth"):
            attach_oauth_httpx_auth(client, _provider())
    finally:
        import asyncio

        asyncio.run(client.aclose())
