"""Provider-neutral OAuth URL and metadata trust checks.

Adapters may use these helpers without importing MCP-specific code.
"""

from __future__ import annotations

from urllib.parse import urlparse


class OAuthMetadataTrustError(ValueError):
    """Raised when an OAuth endpoint crosses the configured trust boundary."""


def normalize_issuer(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise OAuthMetadataTrustError("issuer must be an absolute HTTP(S) URL")
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def validate_endpoint_trust(
    endpoint: str,
    expected_issuer: str,
    *,
    allow_http_localhost: bool = True,
) -> str:
    """Validate an endpoint is HTTPS/local development and same-origin with issuer."""
    normalized_endpoint = normalize_issuer(endpoint)
    parsed = urlparse(normalized_endpoint)
    issuer = urlparse(normalize_issuer(expected_issuer))
    if parsed.scheme != "https":
        if not (
            allow_http_localhost
            and parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise OAuthMetadataTrustError("OAuth endpoint must use HTTPS")
    if parsed.netloc != issuer.netloc:
        raise OAuthMetadataTrustError("OAuth endpoint is outside issuer origin")
    return normalized_endpoint


def validate_redirect_uri(redirect_uri: str, allowed_redirect_uri: str) -> str:
    """Require an exact redirect URI match after URL normalization."""
    actual = redirect_uri.strip()
    expected = allowed_redirect_uri.strip()
    if actual != expected:
        raise OAuthMetadataTrustError("redirect URI mismatch")
    parsed = urlparse(actual)
    if parsed.fragment or parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise OAuthMetadataTrustError("redirect URI is not an absolute HTTP(S) URL")
    return actual
