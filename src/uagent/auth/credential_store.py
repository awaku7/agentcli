from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ..runtime.logging_setup import log_event

if TYPE_CHECKING:
    from .token_store import TokenStore


class CredentialKind(str, Enum):
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    MCP = "mcp"
    A2A = "a2a"
    OTHER = "other"


@dataclass(frozen=True)
class Credential:
    """A named secret without exposing its value through ``repr``."""

    name: str
    kind: CredentialKind
    secret: str = field(repr=False)
    expires_at: int | None = None
    metadata: dict[str, str] = field(default_factory=dict, repr=False)


@runtime_checkable
class CredentialStore(Protocol):
    def get(self, name: str) -> Credential | None:
        ...

    def set(self, credential: Credential, *, name: str | None = None) -> None:
        ...

    def delete(self, name: str) -> bool:
        ...


class InMemoryCredentialStore:
    """Reference implementation used by tests and lightweight runtimes."""

    def __init__(self) -> None:
        self._credentials: dict[str, Credential] = {}

    def get(self, name: str) -> Credential | None:
        _validate_name(name)
        credential = self._credentials.get(name)
        log_event("credential.accessed", credential_name=name, found=credential is not None)
        return credential

    def set(self, credential: Credential, *, name: str | None = None) -> None:
        if not isinstance(credential, Credential):
            raise TypeError("credential must be a Credential")
        _validate_name(credential.name)
        if name is not None and name != credential.name:
            raise ValueError("credential name does not match store name")
        if not credential.secret:
            raise ValueError("credential secret is required")
        self._credentials[credential.name] = credential
        log_event("credential.stored", credential_name=credential.name, kind=credential.kind.value)

    def delete(self, name: str) -> bool:
        _validate_name(name)
        deleted = self._credentials.pop(name, None) is not None
        log_event("credential.deleted", credential_name=name, deleted=deleted)
        return deleted

class PersistentCredentialStore:
    """Encrypted file-backed CredentialStore using the shared TokenStore backend."""

    _ISSUER = "uagent/credential"

    def __init__(self, path: str | Path | None = None, *, encrypt=None, decrypt=None) -> None:
        from .token_store import TokenStore

        if path is None:
            path = os.getenv("UAGENT_CREDENTIAL_STORE_PATH", "") or None
        self._tokens = TokenStore(path, encrypt=encrypt, decrypt=decrypt)

    def get(self, name: str) -> Credential | None:
        _validate_name(name)
        token = self._tokens.load(self._ISSUER, name)
        if token is None:
            log_event("credential.accessed", credential_name=name, found=False)
            return None
        try:
            metadata = json.loads(token.scope or "{}")
            if not isinstance(metadata, dict):
                metadata = {}
        except (TypeError, ValueError):
            metadata = {}
        kind = CredentialKind(token.token_type)
        credential = Credential(
            name=name,
            kind=kind,
            secret=token.access_token,
            expires_at=token.expires_at,
            metadata={str(k): str(v) for k, v in metadata.items()},
        )
        log_event("credential.accessed", credential_name=name, found=True)
        return credential

    def set(self, credential: Credential, *, name: str | None = None) -> None:
        if not isinstance(credential, Credential) or not credential.secret:
            raise ValueError("a non-empty Credential is required")
        _validate_name(credential.name)
        if name is not None and name != credential.name:
            raise ValueError("credential name does not match store name")
        from .token_store import StoredToken

        self._tokens.save(
            self._ISSUER,
            credential.name,
            StoredToken(
                access_token=credential.secret,
                token_type=credential.kind.value,
                expires_at=credential.expires_at,
                refresh_token=credential.metadata.get("refresh_token"),
                scope=json.dumps(credential.metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        log_event("credential.stored", credential_name=credential.name, kind=credential.kind.value)

    def delete(self, name: str) -> bool:
        _validate_name(name)
        deleted = self._tokens.delete(self._ISSUER, name)
        log_event("credential.deleted", credential_name=name, deleted=deleted)
        return deleted

_DEFAULT_CREDENTIAL_STORE: CredentialStore | None = None


def get_default_credential_store() -> CredentialStore:
    """Return the process-wide encrypted store shared by local adapters."""
    global _DEFAULT_CREDENTIAL_STORE
    if _DEFAULT_CREDENTIAL_STORE is None:
        _DEFAULT_CREDENTIAL_STORE = PersistentCredentialStore()
    return _DEFAULT_CREDENTIAL_STORE


class TokenStoreCredentialAdapter:
    """Expose one existing OAuth ``TokenStore`` through ``CredentialStore``."""

    def __init__(
        self,
        token_store: TokenStore,
        *,
        issuer: str,
        resource: str,
        name: str = "oauth/default",
    ) -> None:
        if not issuer or not resource:
            raise ValueError("issuer and resource are required")
        _validate_name(name)
        self._token_store = token_store
        self._issuer = issuer
        self._resource = resource
        self._name = name

    def get(self, name: str) -> Credential | None:
        _validate_name(name)
        if name != self._name:
            return None
        token = self._token_store.load(self._issuer, self._resource)
        if token is None:
            log_event("credential.accessed", credential_name=name, found=False)
            return None
        metadata: dict[str, str] = {
            "token_type": token.token_type,
        }
        if token.refresh_token:
            metadata["refresh_token"] = token.refresh_token
        if token.scope:
            metadata["scope"] = token.scope
        credential = Credential(
            name=self._name,
            kind=CredentialKind.OAUTH_TOKEN,
            secret=token.access_token,
            expires_at=token.expires_at,
            metadata=metadata,
        )
        log_event("credential.accessed", credential_name=name, found=True)
        return credential

    def set(self, credential: Credential, *, name: str | None = None) -> None:
        if credential.kind is not CredentialKind.OAUTH_TOKEN:
            raise ValueError("TokenStore adapter accepts OAUTH_TOKEN credentials only")
        _validate_name(credential.name)
        if name is not None and name != credential.name:
            raise ValueError("credential name does not match store name")
        if credential.name != self._name:
            raise ValueError("credential name does not match adapter name")
        if not credential.secret:
            raise ValueError("credential secret is required")
        from .token_store import StoredToken

        self._token_store.save(
            self._issuer,
            self._resource,
            StoredToken(
                access_token=credential.secret,
                token_type=credential.metadata.get("token_type", "Bearer"),
                expires_at=credential.expires_at,
                refresh_token=credential.metadata.get("refresh_token"),
                scope=credential.metadata.get("scope"),
            ),
        )
        log_event("credential.stored", credential_name=credential.name, kind=credential.kind.value)

    def delete(self, name: str) -> bool:
        _validate_name(name)
        if name != self._name:
            return False
        deleted = self._token_store.delete(self._issuer, self._resource)
        log_event("credential.deleted", credential_name=name, deleted=deleted)
        return deleted


def resolve_credential_secret(
    name: str,
    *,
    kind: CredentialKind,
    store: CredentialStore | None = None,
    environ: Mapping[str, str] | None = None,
    env_names: tuple[str, ...] = (),
) -> str | None:
    """Resolve a credential from the shared store, then environment fallback."""
    _validate_name(name)
    active_store = store or get_default_credential_store()
    if active_store is not None:
        credential = active_store.get(name)
        if credential is not None and credential.kind is kind and credential.secret:
            return credential.secret
    env = environ if environ is not None else os.environ
    for env_name in env_names:
        value = str(env.get(env_name, "") or "").strip()
        if value:
            return value
    return None


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("credential name is required")
