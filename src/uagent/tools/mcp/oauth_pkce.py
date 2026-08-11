"""PKCE primitives for the MCP OAuth authorization-code flow.

No network access, token persistence, or localization belongs here. Callers
must keep the verifier and state in a short-lived protected session.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlencode


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_code_verifier(length: int = 64) -> str:
    """Generate a RFC 7636-compatible high-entropy code verifier."""
    if not 43 <= length <= 128:
        raise ValueError("PKCE verifier length must be between 43 and 128")
    return _b64url(secrets.token_bytes(length))[:length]


def code_challenge_s256(verifier: str) -> str:
    if not verifier or not 43 <= len(verifier) <= 128:
        raise ValueError("invalid PKCE code verifier")
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def generate_state() -> str:
    """Generate an opaque CSRF state value."""
    return _b64url(secrets.token_bytes(32))


def build_authorization_url(
    authorization_endpoint: str,
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
    resource: str | None = None,
) -> str:
    if not authorization_endpoint or not client_id or not redirect_uri:
        raise ValueError(
            "authorization endpoint, client_id, and redirect_uri are required"
        )
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if resource:
        params["resource"] = resource
    separator = "&" if "?" in authorization_endpoint else "?"
    return authorization_endpoint + separator + urlencode(params)


def validate_state(expected: str, received: str) -> bool:
    """Compare OAuth state values without timing leakage."""
    if not expected or not received:
        return False
    return hmac.compare_digest(expected, received)
