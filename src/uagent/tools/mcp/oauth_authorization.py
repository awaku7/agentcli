"""OAuth authorization-session orchestration for MCP HTTP clients.

This internal module does not open browsers, start callback servers, or emit
localized messages. It combines metadata, PKCE, code exchange, and the
encrypted token store while keeping secrets out of serialized state.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import urlencode

from .oauth_flow import OAuthTokenResponse, exchange_authorization_code
from .oauth_metadata import AuthorizationServerMetadata
from ...auth.pkce import (
    build_authorization_url,
    code_challenge_s256,
    generate_code_verifier,
    generate_state,
    validate_state,
)
from ...auth.token_store import StoredToken, TokenStore
from ...auth import Credential, CredentialKind, CredentialStore, get_default_credential_store


@dataclass(frozen=True)
class AuthorizationRequest:
    authorization_url: str
    state: str
    code_verifier: str
    issuer: str
    resource: str
    client_id: str
    redirect_uri: str


class OAuthAuthorizationSession:
    """One-shot PKCE authorization session.

    The verifier is intentionally kept only in memory by this object. Callers
    must retain the object until the redirect callback is received.
    """

    def __init__(
        self,
        *,
        metadata: AuthorizationServerMetadata,
        issuer: str,
        resource: str,
        client_id: str,
        redirect_uri: str,
        scope: str | None = None,
        token_store: TokenStore | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self.metadata = metadata
        self.issuer = issuer
        self.resource = resource
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.token_store = token_store
        self.credential_store = credential_store or (get_default_credential_store() if token_store is None else None)
        self.state = generate_state()
        self.code_verifier = generate_code_verifier()

    def authorization_request(
        self, *, extra_params: dict[str, str] | None = None
    ) -> AuthorizationRequest:
        url = build_authorization_url(
            self.metadata.authorization_endpoint,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            state=self.state,
            code_challenge=code_challenge_s256(self.code_verifier),
            scope=self.scope or "",
            resource=self.resource,
        )
        if extra_params:
            separator = "&" if "?" in url else "?"
            url += separator + urlencode(extra_params)
        return AuthorizationRequest(
            authorization_url=url,
            state=self.state,
            code_verifier=self.code_verifier,
            issuer=self.issuer,
            resource=self.resource,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
        )

    async def complete(
        self,
        *,
        callback_state: str,
        code: str,
        http_client: Any = None,
    ) -> OAuthTokenResponse:
        if not validate_state(self.state, callback_state):
            raise ValueError("OAuth state mismatch")
        token = await exchange_authorization_code(
            self.metadata.token_endpoint,
            code=code,
            code_verifier=self.code_verifier,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            resource=self.resource,
            http_client=http_client,
        )
        expires_at = (
            int(time.time()) + token.expires_in
            if token.expires_in is not None
            else None
        )
        if self.credential_store is not None:
            self.credential_store.set(
                Credential(
                    name=f"mcp/{self.resource}",
                    kind=CredentialKind.OAUTH_TOKEN,
                    secret=token.access_token,
                    expires_at=expires_at,
                    metadata={
                        "token_type": token.token_type,
                        **({"refresh_token": token.refresh_token} if token.refresh_token else {}),
                        **({"scope": token.scope} if token.scope else {}),
                    },
                )
            )
        elif self.token_store is not None:
            self.token_store.save(
                self.issuer,
                self.resource,
                StoredToken(
                    access_token=token.access_token,
                    token_type=token.token_type,
                    expires_at=expires_at,
                    refresh_token=token.refresh_token,
                    scope=token.scope,
                ),
            )
        return token

    def discard(self) -> None:
        """Invalidate this pending session locally."""
        self.state = ""
        self.code_verifier = ""
