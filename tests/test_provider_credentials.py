from __future__ import annotations

from uagent.auth.credential_store import (
    Credential,
    CredentialKind,
    InMemoryCredentialStore,
)
from uagent.auth.provider_credentials import get_provider_credential


def test_provider_credential_prefers_store(monkeypatch) -> None:
    store = InMemoryCredentialStore()
    store.set(
        Credential(
            name="provider/openai",
            kind=CredentialKind.API_KEY,
            secret="stored-key",
        )
    )
    monkeypatch.setenv("UAGENT_OPENAI_API_KEY", "environment-key")

    credential = get_provider_credential("openai", store=store)

    assert credential is not None
    assert credential.secret == "stored-key"


def test_provider_credential_falls_back_to_environment(monkeypatch) -> None:
    monkeypatch.setenv("UAGENT_GROK_API_KEY", "env-key")

    credential = get_provider_credential("grok")

    assert credential is not None
    assert credential.name == "provider/grok"
    assert credential.secret == "env-key"
    assert credential.kind is CredentialKind.API_KEY


def test_provider_credential_rejects_wrong_kind_and_empty_values(monkeypatch) -> None:
    store = InMemoryCredentialStore()
    store.set(
        Credential(
            name="provider/openai",
            kind=CredentialKind.OAUTH_TOKEN,
            secret="oauth-token",
        )
    )
    monkeypatch.setenv("UAGENT_OPENAI_API_KEY", "")

    assert get_provider_credential("openai", store=store) is None
    assert get_provider_credential("unknown-provider") is None
