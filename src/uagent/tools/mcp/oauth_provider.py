"""Runtime OAuth bearer-token provider for MCP HTTP requests."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from .errors import MCPTransportError
from .oauth_flow import refresh_access_token
from .token_store import StoredToken, TokenStore


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

    async def authorization_header(self, force_refresh: bool = False) -> str:
        token = self.token_store.load(self.issuer, self.resource)
        if token is None:
            raise MCPTransportError(
                "MCP_OAUTH_TOKEN_MISSING", "oauth/authorize", {"resource": self.resource}
            )
        if force_refresh or token.expired(int(time.time())):
            if not token.refresh_token:
                raise MCPTransportError(
                    "MCP_OAUTH_REFRESH_TOKEN_MISSING", "oauth/refresh", {}
                )
            token = await self._refresh(token)
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
        self.token_store.save(self.issuer, self.resource, token)
        return token


AuthorizationHeaderProvider = Callable[[bool], Awaitable[str]]


async def stored_token_authorization_header(
    provider: OAuthTokenProvider, force_refresh: bool = False
) -> str:
    """Adapter suitable for ``StatelessHTTPClient.authorization_provider``."""
    return await provider.authorization_header(force_refresh)


__all__ = ["AuthorizationHeaderProvider", "OAuthTokenProvider", "stored_token_authorization_header"]