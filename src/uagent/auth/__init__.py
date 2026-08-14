"""Shared authentication primitives for connector adapters."""

from .oauth_common import (
    OAuthMetadataTrustError,
    normalize_issuer,
    validate_endpoint_trust,
    validate_redirect_uri,
)

__all__ = [
    "OAuthMetadataTrustError",
    "normalize_issuer",
    "validate_endpoint_trust",
    "validate_redirect_uri",
]
