"""End-to-end local-browser OAuth authorization flow for MCP."""

from __future__ import annotations

import inspect
import webbrowser
from collections.abc import Callable
from typing import Any

from .oauth_authorization import OAuthAuthorizationSession
from .oauth_callback import OAuthCallbackListener
from .oauth_flow import OAuthTokenResponse
from .oauth_metadata import AuthorizationServerMetadata
from ...auth.token_store import TokenStore
from ...auth import CredentialStore


async def authorize_with_local_callback(
    *,
    metadata: AuthorizationServerMetadata,
    issuer: str,
    resource: str,
    client_id: str,
    scope: str | None = None,
    token_store: TokenStore | None = None,
    credential_store: CredentialStore | None = None,
    http_client: Any = None,
    callback_path: str = "/callback",
    timeout: float = 300,
    browser_opener: Callable[[str], Any] | None = None,
) -> OAuthTokenResponse:
    """Open the browser, receive one local redirect, and exchange the code."""
    opener = browser_opener or webbrowser.open
    async with OAuthCallbackListener(path=callback_path) as listener:
        session = OAuthAuthorizationSession(
            metadata=metadata,
            issuer=issuer,
            resource=resource,
            client_id=client_id,
            redirect_uri=listener.redirect_uri,
            scope=scope,
            token_store=token_store,
            credential_store=credential_store,
        )
        request = session.authorization_request()
        result = opener(request.authorization_url)
        if inspect.isawaitable(result):
            await result
        callback = await listener.wait(timeout=timeout)
        if callback.error:
            description = callback.error_description or "OAuth authorization failed"
            raise ValueError(f"{callback.error}: {description}")
        if not callback.code or not callback.state:
            raise ValueError("OAuth callback did not contain code and state")
        return await session.complete(
            callback_state=callback.state,
            code=callback.code,
            http_client=http_client,
        )


__all__ = ["authorize_with_local_callback"]
