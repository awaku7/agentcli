from __future__ import annotations

from uagent.a2a.client import A2AClient
from uagent.a2a.server import build_app
from uagent.auth import Credential, CredentialKind, InMemoryCredentialStore


def _store() -> InMemoryCredentialStore:
    store = InMemoryCredentialStore()
    store.set(
        Credential(
            name="a2a/default",
            kind=CredentialKind.A2A,
            secret="stored-token",
        )
    )
    return store


def test_a2a_client_prefers_credential_store() -> None:
    client = A2AClient(
        base_url="http://a2a.example",
        credential_store=_store(),
    )
    try:
        assert client.token == "stored-token"
        assert client._auth_headers() == {"Authorization": "Bearer stored-token"}
    finally:
        client.close()


def test_a2a_app_accepts_shared_credential_store() -> None:
    app = build_app(credential_store=_store())
    assert app.state.credential_store.get("a2a/default").secret == "stored-token"
