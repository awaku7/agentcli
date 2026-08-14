from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from uagent.auth.credential_store import (
    Credential,
    CredentialKind,
    CredentialStore,
    InMemoryCredentialStore,
)


def test_credential_does_not_expose_secret_in_repr() -> None:
    credential = Credential(
        name="openai",
        kind=CredentialKind.API_KEY,
        secret="super-secret",
    )

    assert "super-secret" not in repr(credential)
    assert credential.kind is CredentialKind.API_KEY

    with pytest.raises(FrozenInstanceError):
        credential.secret = "changed"  # type: ignore[misc]


def test_in_memory_store_round_trip_and_delete() -> None:
    store: CredentialStore = InMemoryCredentialStore()
    credential = Credential(
        name="mcp/example",
        kind=CredentialKind.OAUTH_TOKEN,
        secret="token-value",
        expires_at=123,
    )

    assert store.get("mcp/example") is None
    store.set(credential)
    assert store.get("mcp/example") == credential
    assert store.delete("mcp/example") is True
    assert store.get("mcp/example") is None
    assert store.delete("mcp/example") is False


def test_store_rejects_name_mismatch() -> None:
    store = InMemoryCredentialStore()
    credential = Credential(
        name="actual",
        kind=CredentialKind.API_KEY,
        secret="value",
    )

    with pytest.raises(ValueError, match="name"):
        store.set(credential, name="other")


def test_store_rejects_empty_names_and_secrets() -> None:
    store = InMemoryCredentialStore()

    with pytest.raises(ValueError):
        store.get("")
    with pytest.raises(ValueError):
        store.set(Credential(name="", kind=CredentialKind.API_KEY, secret="v"))
    with pytest.raises(ValueError):
        store.set(Credential(name="x", kind=CredentialKind.API_KEY, secret=""))
