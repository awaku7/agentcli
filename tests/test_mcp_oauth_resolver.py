from __future__ import annotations

import pytest

from uagent.tools.mcp.errors import MCPProtocolError
from uagent.tools.mcp.oauth_metadata import (
    authorization_server_metadata_urls,
    protected_resource_metadata_urls,
    validate_oauth_transport,
)


def test_metadata_candidates_are_path_aware_and_deduplicated() -> None:
    assert protected_resource_metadata_urls("https://mcp.example/mcp") == (
        "https://mcp.example/.well-known/oauth-protected-resource/mcp",
        "https://mcp.example/.well-known/oauth-protected-resource",
    )
    assert authorization_server_metadata_urls("https://auth.example/tenant") == (
        "https://auth.example/.well-known/oauth-authorization-server/tenant",
        "https://auth.example/.well-known/oauth-authorization-server",
    )


def test_oauth_transport_allows_https_and_localhost_http_only() -> None:
    validate_oauth_transport("https://auth.example")
    validate_oauth_transport("http://localhost:8000")
    with pytest.raises(MCPProtocolError) as exc_info:
        validate_oauth_transport("http://auth.example")
    assert exc_info.value.code == "MCP_INSECURE_OAUTH_URL"
