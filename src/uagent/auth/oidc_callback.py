"""OIDC authorization-code callback orchestration.

This module connects a browser-bound, single-use authorization transaction to
the token endpoint and verifies the returned ID token before producing an
IdentityContext. It deliberately does not create a Web session or cookie.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .oidc_transactions import OIDCTransactionStore
from .oidc_verifier import (
    OIDCProviderMetadata,
    fetch_jwks,
    resolve_entra_group_overage,
    verify_id_token_with_overage,
)
from ..env_utils import env_get
from ..runtime.identity_context import IdentityContext, IdentityResolutionError


@dataclass(frozen=True)
class OIDCTokenResponse:
    id_token: str
    access_token: str = ""
    token_type: str = ""


async def _exchange_code(
    *,
    metadata: OIDCProviderMetadata,
    code: str,
    code_verifier: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    http_client: Any,
) -> OIDCTokenResponse:
    if not code or not client_id or not redirect_uri:
        raise IdentityResolutionError("incomplete OIDC code exchange input")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        response = await http_client.post(
            metadata.token_endpoint,
            data=data,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise IdentityResolutionError("OIDC token exchange failed") from exc
    if not isinstance(payload, dict):
        raise IdentityResolutionError("invalid OIDC token response")
    id_token = payload.get("id_token")
    if not isinstance(id_token, str) or not id_token or len(id_token) > 16_384:
        raise IdentityResolutionError("OIDC token response missing ID token")
    access_token = payload.get("access_token", "")
    token_type = payload.get("token_type", "")
    if access_token is None:
        access_token = ""
    if token_type is None:
        token_type = ""
    if not isinstance(access_token, str) or len(access_token) > 65_536:
        raise IdentityResolutionError("invalid OIDC access token response")
    if not isinstance(token_type, str):
        raise IdentityResolutionError("invalid OIDC token type")
    if access_token and token_type.lower() != "bearer":
        raise IdentityResolutionError("unsupported OIDC access token type")
    return OIDCTokenResponse(
        id_token=id_token,
        access_token=access_token,
        token_type=token_type,
    )


async def complete_authorization_callback(
    *,
    store: OIDCTransactionStore,
    metadata: OIDCProviderMetadata,
    state: str,
    browser_binding: str,
    code: str,
    client_id: str,
    redirect_uri: str,
    http_client: Any,
    client_secret: str = "",
    jwks: dict | None = None,
) -> IdentityContext:
    """Consume one callback and return only a cryptographically verified identity."""
    try:
        transaction = store.consume(state=state, browser_binding=browser_binding)
    except ValueError as exc:
        raise IdentityResolutionError("invalid OIDC authorization callback") from exc
    token = await _exchange_code(
        metadata=metadata,
        code=code,
        code_verifier=transaction.code_verifier,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        http_client=http_client,
    )
    signing_keys = jwks if jwks is not None else fetch_jwks(metadata)
    identity, group_overage = verify_id_token_with_overage(
        token.id_token,
        metadata=metadata,
        jwks=signing_keys,
        client_id=client_id,
        nonce=transaction.nonce,
    )
    if not group_overage:
        return identity
    groups = await resolve_entra_group_overage(
        identity,
        token.access_token,
        http_client=http_client,
        configured_scopes=str(env_get("UAGENT_OIDC_GRAPH_SCOPE", "") or ""),
    )
    return replace(identity, groups=groups)


__all__ = ["OIDCTokenResponse", "complete_authorization_callback"]
