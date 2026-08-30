from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from uagent.auth import (
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


def test_token_store_adapter_round_trip(tmp_path) -> None:
    from uagent.auth.credential_store import TokenStoreCredentialAdapter
    from uagent.auth.token_store import TokenStore

    tokens = TokenStore(
        tmp_path / "tokens.json",
        encrypt=lambda value: f"enc:{value}",
        decrypt=lambda value: value.removeprefix("enc:"),
    )
    store = TokenStoreCredentialAdapter(
        tokens,
        issuer="https://issuer.example",
        resource="https://resource.example/mcp",
        name="mcp/example",
    )
    credential = Credential(
        name="mcp/example",
        kind=CredentialKind.OAUTH_TOKEN,
        secret="access-token",
        expires_at=123,
        metadata={
            "token_type": "Bearer",
            "refresh_token": "refresh-token",
            "scope": "mcp.read",
        },
    )

    store.set(credential)
    loaded = store.get("mcp/example")

    assert loaded == credential
    assert store.delete("mcp/example") is True
    assert store.get("mcp/example") is None


def test_token_store_adapter_rejects_non_oauth_credentials(tmp_path) -> None:
    from uagent.auth.credential_store import TokenStoreCredentialAdapter
    from uagent.auth.token_store import TokenStore

    tokens = TokenStore(
        tmp_path / "tokens.json",
        encrypt=lambda value: value,
        decrypt=lambda value: value,
    )
    store = TokenStoreCredentialAdapter(
        tokens,
        issuer="issuer",
        resource="resource",
    )

    with pytest.raises(ValueError, match="OAUTH_TOKEN"):
        store.set(
            Credential(name="oauth/default", kind=CredentialKind.API_KEY, secret="key")
        )


def test_persistent_credential_store_round_trip(tmp_path) -> None:
    from uagent.auth import PersistentCredentialStore

    path = tmp_path / "credentials.json"
    first = PersistentCredentialStore(
        path,
        encrypt=lambda value: f"enc:{value}",
        decrypt=lambda value: value.removeprefix("enc:"),
    )
    first.set(
        Credential(
            name="a2a/default",
            kind=CredentialKind.A2A,
            secret="persisted",
            metadata={"source": "test"},
        )
    )

    second = PersistentCredentialStore(
        path,
        encrypt=lambda value: f"enc:{value}",
        decrypt=lambda value: value.removeprefix("enc:"),
    )
    credential = second.get("a2a/default")
    assert credential is not None
    assert credential.secret == "persisted"
    assert credential.kind is CredentialKind.A2A
    assert credential.metadata == {"source": "test"}


def test_os_credential_store_rejects_fail_backend() -> None:
    from uagent.auth import OSCredentialStore

    class NoBackend:
        @staticmethod
        def get_keyring():
            class Backend:
                priority = 0

            return Backend()

    with pytest.raises(RuntimeError, match="No usable OS keyring backend"):
        OSCredentialStore(keyring_module=NoBackend)


def test_os_credential_store_round_trip() -> None:
    from uagent.auth import OSCredentialStore

    class Keyring:
        values: dict[tuple[str, str], str] = {}

        @classmethod
        def get_password(cls, service: str, name: str) -> str | None:
            return cls.values.get((service, name))

        @classmethod
        def set_password(cls, service: str, name: str, value: str) -> None:
            cls.values[(service, name)] = value

        @classmethod
        def delete_password(cls, service: str, name: str) -> None:
            del cls.values[(service, name)]

    store = OSCredentialStore(keyring_module=Keyring)
    store.set(
        Credential(
            name="provider/openai",
            kind=CredentialKind.API_KEY,
            secret="secret-value",
            expires_at=123,
            metadata={"source": "keychain"},
        )
    )

    credential = store.get("provider/openai")
    assert credential is not None
    assert credential.secret == "secret-value"
    assert credential.expires_at == 123
    assert credential.metadata == {"source": "keychain"}
    assert store.delete("provider/openai") is True
    assert store.get("provider/openai") is None
