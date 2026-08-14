"""Runtime OAuth bearer-token provider for MCP HTTP requests."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Awaitable, Callable

import httpx

from .errors import MCPTransportError
from .oauth_flow import refresh_access_token
from ...auth.token_store import StoredToken, TokenStore


class OAuthTokenProvider:
    """Load, refresh, and persist an MCP OAuth access token."""

    def __init__(
        self,
        *,
        issuer: str,
        resource: str,
        client_id: str,
        token_endpoint: str,
        token_store: TokenStore,
        http_client: Any,
    ) -> None:
        self.issuer = issuer
        self.resource = resource
        self.client_id = client_id
        self.token_endpoint = token_endpoint
        self.token_store = token_store
        self.http_client = http_client
        self._refresh_lock = asyncio.Lock()

    async def authorization_header(self, force_refresh: bool = False) -> str:
        token = self.token_store.load(self.issuer, self.resource)
        if token is None:
            raise MCPTransportError(
                "MCP_OAUTH_TOKEN_MISSING",
                "oauth/authorize",
                {"resource": self.resource},
            )
        if force_refresh or token.expired(int(time.time())):
            async with self._refresh_lock:
                lock = self.token_store.write_lock()
                await asyncio.to_thread(lock.__enter__)
                try:
                    current = self.token_store.load(self.issuer, self.resource)
                    now = int(time.time())
                    if (
                        current is not None
                        and current != token
                        and not current.expired(now)
                    ):
                        token = current
                    else:
                        previous = current or token
                        if not previous.refresh_token:
                            raise MCPTransportError(
                                "MCP_OAUTH_REFRESH_TOKEN_MISSING", "oauth/refresh", {}
                            )
                        token = await self._refresh(previous)
                        self.token_store.save_locked(self.issuer, self.resource, token)
                finally:
                    await asyncio.to_thread(lock.__exit__, None, None, None)
        return f"{token.token_type} {token.access_token}"

    async def _refresh(self, previous: StoredToken) -> StoredToken:
        response = await refresh_access_token(
            self.token_endpoint,
            refresh_token=previous.refresh_token or "",
            client_id=self.client_id,
            resource=self.resource,
            http_client=self.http_client,
        )
        token = StoredToken(
            access_token=response.access_token,
            token_type=response.token_type,
            expires_at=(
                int(time.time()) + response.expires_in
                if response.expires_in is not None
                else None
            ),
            refresh_token=response.refresh_token or previous.refresh_token,
            scope=response.scope or previous.scope,
        )
        return token


class MCPOAuthHTTPXAuth(httpx.Auth):
    """httpx async auth hook for SDK Streamable HTTP transports."""

    requires_request_body = True

    def __init__(self, provider: "OAuthTokenProvider") -> None:
        self.provider = provider

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = await self.provider.authorization_header(
            False
        )
        response = yield request
        if response.status_code == 401:
            request.headers["Authorization"] = await self.provider.authorization_header(
                True
            )
            yield request


def attach_oauth_httpx_auth(http_client: Any, provider: "OAuthTokenProvider") -> Any:
    """Attach OAuth auth to a caller-owned httpx client without overwriting auth."""
    existing = getattr(http_client, "auth", None)
    if existing is not None and not isinstance(existing, MCPOAuthHTTPXAuth):
        raise ValueError("http_client already has a conflicting auth configuration")
    http_client.auth = MCPOAuthHTTPXAuth(provider)
    return http_client


AuthorizationHeaderProvider = Callable[[bool], Awaitable[str]]


async def stored_token_authorization_header(
    provider: OAuthTokenProvider, force_refresh: bool = False
) -> str:
    """Adapter suitable for ``StatelessHTTPClient.authorization_provider``."""
    return await provider.authorization_header(force_refresh)


__all__ = [
    "AuthorizationHeaderProvider",
    "MCPOAuthHTTPXAuth",
    "attach_oauth_httpx_auth",
    "OAuthTokenProvider",
    "stored_token_authorization_header",
]
