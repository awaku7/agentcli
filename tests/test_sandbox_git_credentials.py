"""Host-only Git credentials: user inheritance and session isolation."""

from __future__ import annotations

import time

import pytest

from uagent.auth.credential_store import (
    Credential,
    CredentialKind,
    InMemoryCredentialStore,
)
from uagent.runtime import mxc_backend, sandbox_git_credentials
from uagent.runtime.execution_broker import TrustedSandboxScope


@pytest.fixture
def store():
    return InMemoryCredentialStore()


@pytest.fixture
def cli(monkeypatch, tmp_path):
    monkeypatch.setattr(mxc_backend, "_trusted_local_principal", lambda: "os-uid:42")
    return mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="session-a"
    )


def test_cli_and_gui_share_user_default_but_override_separately(
    monkeypatch, tmp_path, cli, store
):
    gui = mxc_backend.startup_scope(
        entry_point="gui", project_path=str(tmp_path), session_id="session-a"
    )
    sandbox_git_credentials.save_git_https_token(
        cli, "default", "user-token", store=store
    )
    sandbox_git_credentials.select_git_credential(cli, "user", "default", store=store)
    assert (
        sandbox_git_credentials.effective_git_credential_alias(gui, store=store)
        == "default"
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(gui, store=store)
        == "user-token"
    )

    sandbox_git_credentials.save_git_https_token(
        cli, "project", "project-token", store=store
    )
    sandbox_git_credentials.select_git_credential(
        cli, "session", "project", store=store
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)
        == "project-token"
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(gui, store=store)
        == "user-token"
    )


def test_session_override_can_disable_and_reset(cli, store):
    sandbox_git_credentials.save_git_https_token(cli, "main", "token", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "main", store=store)
    sandbox_git_credentials.select_git_credential(cli, "session", None, store=store)
    assert (
        sandbox_git_credentials.effective_git_credential_alias(cli, store=store) is None
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)
        is None
    )
    assert sandbox_git_credentials.reset_git_credential_selection(
        cli, "session", store=store
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)
        == "token"
    )


def test_web_and_a2a_are_isolated_even_with_matching_principal(cli, store):
    web = TrustedSandboxScope(
        "web",
        cli.principal_id,
        cli.project_id,
        "web-room",
        "room-a",
        settings_session_id="room-a",
    )
    a2a = TrustedSandboxScope(
        "a2a",
        cli.principal_id,
        cli.project_id,
        "a2a-task",
        "task-a",
        settings_session_id="task-a",
    )
    sandbox_git_credentials.save_git_https_token(
        cli, "work", "local-token", store=store
    )
    sandbox_git_credentials.select_git_credential(cli, "user", "work", store=store)
    sandbox_git_credentials.select_git_credential(web, "user", "work", store=store)
    with pytest.raises(PermissionError, match="not available"):
        sandbox_git_credentials.resolve_git_https_token_for_host(web, store=store)
    assert (
        sandbox_git_credentials.effective_git_credential_alias(a2a, store=store) is None
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)
        == "local-token"
    )


def test_different_principals_cannot_access_same_alias(cli, store):
    other = TrustedSandboxScope(
        "cli",
        "os-uid:43",
        cli.project_id,
        "cli-session",
        "session-a",
        settings_session_id="session-a",
    )
    sandbox_git_credentials.save_git_https_token(cli, "same", "alice", store=store)
    sandbox_git_credentials.save_git_https_token(other, "same", "bob", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "same", store=store)
    sandbox_git_credentials.select_git_credential(other, "user", "same", store=store)
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)
        == "alice"
    )
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(other, store=store)
        == "bob"
    )


def test_credential_selection_survives_recreated_process_scope(
    monkeypatch, tmp_path, cli, store
):
    sandbox_git_credentials.save_git_https_token(cli, "work", "secret", store=store)
    sandbox_git_credentials.select_git_credential(cli, "session", "work", store=store)
    monkeypatch.setattr(mxc_backend.os, "getpid", lambda: 123456)
    resumed = mxc_backend.startup_scope(
        entry_point="cli", project_path=str(tmp_path), session_id="session-a"
    )
    assert cli.scope_id != resumed.scope_id
    assert (
        sandbox_git_credentials.resolve_git_https_token_for_host(resumed, store=store)
        == "secret"
    )


def test_credential_deletion_prevents_use_and_does_not_fallback(cli, store):
    sandbox_git_credentials.save_git_https_token(cli, "work", "secret", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "work", store=store)
    assert sandbox_git_credentials.remove_git_https_token(cli, "work", store=store)
    with pytest.raises(PermissionError, match="not available"):
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)


def test_invalid_selection_does_not_fallback_to_user_default(cli, store):
    sandbox_git_credentials.save_git_https_token(cli, "work", "secret", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "work", store=store)
    sandbox_git_credentials.select_git_credential(cli, "session", "work", store=store)
    key = sandbox_git_credentials._selection_key(cli, "session")
    store.set(Credential(key, CredentialKind.OTHER, "work"))
    with pytest.raises(PermissionError, match="invalid"):
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)


def test_expired_token_is_rejected(cli, store):
    sandbox_git_credentials.save_git_https_token(cli, "old", "secret", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "old", store=store)
    key = sandbox_git_credentials._token_key(cli, "old")
    store.set(
        Credential(
            key,
            CredentialKind.OTHER,
            "secret",
            expires_at=int(time.time()) - 1,
            metadata={"purpose": sandbox_git_credentials._TOKEN_PURPOSE},
        )
    )
    with pytest.raises(PermissionError, match="expired"):
        sandbox_git_credentials.resolve_git_https_token_for_host(cli, store=store)


@pytest.mark.parametrize("alias", ["", "../../other", "a/b", "with spaces", "x" * 65])
def test_invalid_alias_is_rejected(cli, store, alias):
    with pytest.raises(ValueError):
        sandbox_git_credentials.save_git_https_token(cli, alias, "value", store=store)
    with pytest.raises(ValueError):
        sandbox_git_credentials.select_git_credential(cli, "user", alias, store=store)


def test_git_credential_does_not_enter_sandbox_settings(
    monkeypatch, tmp_path, cli, store
):
    from uagent.runtime import mxc_session_settings

    sandbox_git_credentials.save_git_https_token(cli, "work", "top-secret", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "work", store=store)
    monkeypatch.setattr(mxc_backend, "_local_app_data", lambda: tmp_path)
    assert mxc_backend._session_settings_environment(cli) == {}
    assert mxc_session_settings.effective_environment(tmp_path, cli) == {}
    assert not list(tmp_path.rglob("*.json"))


def test_credentials_are_not_exposed_by_selection_metadata(cli, store):
    sandbox_git_credentials.save_git_https_token(cli, "work", "top-secret", store=store)
    sandbox_git_credentials.select_git_credential(cli, "user", "work", store=store)
    alias = sandbox_git_credentials.effective_git_credential_alias(cli, store=store)
    assert alias == "work"
    assert "top-secret" not in repr(
        store.get(sandbox_git_credentials._token_key(cli, alias))
    )
