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


def test_provider_credential_source_distinguishes_explicit_and_generic_environment(
    monkeypatch,
) -> None:
    from uagent.auth.provider_credentials import get_provider_credential_source

    monkeypatch.setenv("UAGENT_GROK_API_KEY", "explicit")
    assert get_provider_credential_source("grok") == "explicit_environment"

    monkeypatch.delenv("UAGENT_GROK_API_KEY")
    monkeypatch.setenv("XAI_API_KEY", "generic")
    assert get_provider_credential_source("grok") == "environment"


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


def test_optional_local_provider_ignores_strict_missing_env_getter() -> None:
    def strict_getter(name: str) -> str:
        raise ValueError(f"Environment variable {name} is not set.")

    assert get_provider_credential("lmstudio", env_getter=strict_getter) is None


def test_typesafe_decision_credential_uses_decision_environment_name(
    monkeypatch,
) -> None:
    monkeypatch.setenv("UAGENT_DECISION_TYPESAFE_API_KEY", "decision-key")

    credential = get_provider_credential("typesafe")

    assert credential is not None
    assert credential.name == "provider/typesafe"
    assert credential.secret == "decision-key"


def test_perplexity_credential_accepts_official_environment_name(monkeypatch) -> None:
    monkeypatch.delenv("UAGENT_PERPLEXITY_API_KEY", raising=False)
    monkeypatch.setenv("PERPLEXITY_API_KEY", "router-key")

    credential = get_provider_credential("perplexity")

    assert credential is not None
    assert credential.name == "provider/perplexity"
    assert credential.secret == "router-key"
