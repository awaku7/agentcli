from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from uagent.tools.mcp.oauth_authorization import OAuthAuthorizationSession
from uagent.tools.mcp.oauth_metadata import AuthorizationServerMetadata
from uagent.tools.mcp.token_store import TokenStore


def test_authorization_session_builds_pkce_url_and_stores_token(tmp_path: Path) -> None:
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
        session = OAuthAuthorizationSession(
            metadata=metadata,
            issuer=metadata.issuer,
            resource="https://mcp.example/mcp",
            client_id="uag",
            redirect_uri="http://127.0.0.1/callback",
            scope="mcp:read",
            token_store=store,
        )
        request = session.authorization_request()
        assert "code_challenge_method=S256" in request.authorization_url
        assert request.state == session.state

        def handler(http_request: httpx.Request) -> httpx.Response:
            body = dict(
                pair.split("=", 1)
                for pair in http_request.content.decode().split("&")
            )
            assert body["code"] == "code-1"
            assert body["code_verifier"] == request.code_verifier
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "token_type": "Bearer",
                    "refresh_token": "refresh-1",
                    "expires_in": 300,
                    "scope": "mcp:read",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            token = await session.complete(
                callback_state=request.state,
                code="code-1",
                http_client=client,
            )
        assert token.access_token == "access-1"
        assert store.load(metadata.issuer, "https://mcp.example/mcp").refresh_token == "refresh-1"
        assert json.loads((tmp_path / "tokens.json").read_text())

    asyncio.run(scenario())


def test_authorization_session_rejects_state_mismatch() -> None:
    async def scenario() -> None:
        metadata = AuthorizationServerMetadata(
            issuer="https://auth.example",
            authorization_endpoint="https://auth.example/authorize",
            token_endpoint="https://auth.example/token",
            registration_endpoint=None,
            scopes_supported=(),
            raw={},
        )
        session = OAuthAuthorizationSession(
            metadata=metadata,
            issuer=metadata.issuer,
            resource="https://mcp.example/mcp",
            client_id="uag",
            redirect_uri="http://127.0.0.1/callback",
        )
        try:
            await session.complete(callback_state="wrong", code="code")
        except ValueError as exc:
            assert str(exc) == "OAuth state mismatch"
        else:
            raise AssertionError("state mismatch was accepted")

    asyncio.run(scenario())
