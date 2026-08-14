"""Shared authentication primitives for connector adapters."""

from .credential_store import (
    Credential,
    CredentialKind,
    CredentialStore,
    InMemoryCredentialStore,
)
from .oauth_common import (
    OAuthMetadataTrustError,
    normalize_issuer,
    validate_endpoint_trust,
    validate_redirect_uri,
)

__all__ = [
    "Credential",
    "CredentialKind",
    "CredentialStore",
    "InMemoryCredentialStore",
    "OAuthMetadataTrustError",
    "normalize_issuer",
    "validate_endpoint_trust",
    "validate_redirect_uri",
]
