"""Shared OAuth PKCE/state primitives.

The MCP adapter remains the compatibility implementation for now; this module
provides the provider-neutral import path used by future connectors.
"""

from uagent.tools.mcp.oauth_pkce import (
    build_authorization_url,
    code_challenge_s256,
    generate_code_verifier,
    generate_state,
    validate_state,
)

__all__ = [
    "build_authorization_url",
    "code_challenge_s256",
    "generate_code_verifier",
    "generate_state",
    "validate_state",
]
