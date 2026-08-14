"""Runtime OAuth bearer-token provider for MCP HTTP requests."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Awaitable, Callable

import httpx

from ...auth.credential_store import Credential, CredentialKind, CredentialStore, get_default_credential_store
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
        credential_store: CredentialStore | None = None,
        credential_name: str | None = None,
    ) -> None:
        self.issuer = issuer
        self.resource = resource
        self.client_id = client_id
        self.token_endpoint = token_endpoint
        self.token_store = token_store
        self.http_client = http_client
        self._refresh_lock = asyncio.Lock()
        self.credential_store = credential_store or get_default_credential_store()
        self._credential_selected = credential_store is not None
        self.credential_name = credential_name or f"mcp/{resource}"

    def _load_token(self) -> StoredToken | None:
        credential = self.credential_store.get(self.credential_name)
        if credential is None:
            if self._credential_selected:
                return None
            return self.token_store.load(self.issuer, self.resource)
        self._credential_selected = True
        return StoredToken(
            access_token=credential.secret,
            token_type=credential.metadata.get("token_type", "Bearer"),
            expires_at=credential.expires_at,
            refresh_token=credential.metadata.get("refresh_token"),
            scope=credential.metadata.get("scope"),
        )

    def _save_token(self, token: StoredToken) -> None:
        if not self._credential_selected:
            self.token_store.save_locked(self.issuer, self.resource, token)
            return
        self.credential_store.set(
            Credential(
                name=self.credential_name,
                kind=CredentialKind.OAUTH_TOKEN,
                secret=token.access_token,
                expires_at=token.expires_at,
                metadata={
                    "token_type": token.token_type,
                    **({"refresh_token": token.refresh_token} if token.refresh_token else {}),
                    **({"scope": token.scope} if token.scope else {}),
                },
            )
        )

    async def authorization_header(self, force_refresh: bool = False) -> str:
        token = self._load_token()
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
                    current = self._load_token()
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
                        self._save_token(token)
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
