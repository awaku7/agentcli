"""Shared authentication primitives for connector adapters."""

from .credential_store import (
    Credential,
    CredentialKind,
    CredentialStore,
    get_default_credential_store,
    InMemoryCredentialStore,
    OSCredentialStore,
    PersistentCredentialStore,
    TokenStoreCredentialAdapter,
    resolve_credential_secret,
)
from .provider_credentials import get_provider_api_key, get_provider_credential
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
    "get_default_credential_store",
    "InMemoryCredentialStore",
    "OSCredentialStore",
    "PersistentCredentialStore",
    "TokenStoreCredentialAdapter",
    "resolve_credential_secret",
    "get_provider_api_key",
    "get_provider_credential",
    "OAuthMetadataTrustError",
    "normalize_issuer",
    "validate_endpoint_trust",
    "validate_redirect_uri",
]
