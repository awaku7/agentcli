from __future__ import annotations

from uagent.tools.mcp.oauth_authorization import OAuthAuthorizationSession
from uagent.tools.mcp.oauth_metadata import AuthorizationServerMetadata


def test_authorization_request_includes_extra_params() -> None:
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
        client_id="client",
        redirect_uri="http://127.0.0.1/callback",
    )
    request = session.authorization_request(extra_params={"audience": "mcp api"})
    assert "audience=mcp+api" in request.authorization_url
