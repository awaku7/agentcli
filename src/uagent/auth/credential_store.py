from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

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
        return self._credentials.get(name)

    def set(self, credential: Credential, *, name: str | None = None) -> None:
        if not isinstance(credential, Credential):
            raise TypeError("credential must be a Credential")
        _validate_name(credential.name)
        if name is not None and name != credential.name:
            raise ValueError("credential name does not match store name")
        if not credential.secret:
            raise ValueError("credential secret is required")
        self._credentials[credential.name] = credential

    def delete(self, name: str) -> bool:
        _validate_name(name)
        return self._credentials.pop(name, None) is not None


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
            return None
        metadata: dict[str, str] = {
            "token_type": token.token_type,
        }
        if token.refresh_token:
            metadata["refresh_token"] = token.refresh_token
        if token.scope:
            metadata["scope"] = token.scope
        return Credential(
            name=self._name,
            kind=CredentialKind.OAUTH_TOKEN,
            secret=token.access_token,
            expires_at=token.expires_at,
            metadata=metadata,
        )

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

    def delete(self, name: str) -> bool:
        _validate_name(name)
        if name != self._name:
            return False
        return self._token_store.delete(self._issuer, self._resource)


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("credential name is required")
