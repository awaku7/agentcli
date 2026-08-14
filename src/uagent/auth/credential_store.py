from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


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


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("credential name is required")
