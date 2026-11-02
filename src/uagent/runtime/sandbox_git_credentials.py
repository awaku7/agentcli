"""Host-only Git credential references for MXC user and session scopes.

Credential material lives in UAG's CredentialStore, never sandbox environment,
workspace files, command arguments, or tool results. The network Git broker
will consume these APIs only after validating the current trusted scope.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from ..auth.credential_store import (
    Credential,
    CredentialKind,
    CredentialStore,
    get_default_credential_store,
)
from .execution_broker import TrustedSandboxScope
from .mxc_session_settings import settings_path

_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SELECTION_PURPOSE = "sandbox_git_credential_selection_v1"
_TOKEN_PURPOSE = "sandbox_git_https_token_v1"
_SELECTION_NONE = "disabled"


def _store(store: CredentialStore | None) -> CredentialStore:
    return store if store is not None else get_default_credential_store()


def _owner_prefix(scope: TrustedSandboxScope) -> str:
    # Stable user identity reuses the same realm policy as environment
    # profiles: CLI/GUI share a local OS principal, Web/A2A remain distinct.
    digest = settings_path(Path("."), scope, "user").stem
    return f"sandbox/git/v1/{digest}"


def _selection_key(scope: TrustedSandboxScope, level: str) -> str:
    if level not in {"user", "session"}:
        raise ValueError("Git credential selection level must be user or session")
    digest = settings_path(Path("."), scope, level).stem
    return f"{_owner_prefix(scope)}/selection/{level}/{digest}"


def _token_key(scope: TrustedSandboxScope, alias: str) -> str:
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ValueError("Git credential alias must be 1–64 safe characters")
    return f"{_owner_prefix(scope)}/token/{alias}"


def save_git_https_token(
    scope: TrustedSandboxScope,
    alias: str,
    token: str,
    *,
    store: CredentialStore | None = None,
) -> None:
    """Register an HTTPS token for this *user*, from a trusted host UI only."""
    name = _token_key(scope, alias)
    if not isinstance(token, str) or not token or "\0" in token:
        raise ValueError("a nonempty Git HTTPS token is required")
    _store(store).set(
        Credential(
            name=name,
            kind=CredentialKind.OTHER,
            secret=token,
            metadata={"purpose": _TOKEN_PURPOSE},
        )
    )


def remove_git_https_token(
    scope: TrustedSandboxScope,
    alias: str,
    *,
    store: CredentialStore | None = None,
) -> bool:
    """Revoke one owner's token; it cannot revoke another principal's token."""
    return _store(store).delete(_token_key(scope, alias))


def select_git_credential(
    scope: TrustedSandboxScope,
    level: str,
    alias: str | None,
    *,
    store: CredentialStore | None = None,
) -> None:
    """Choose a user default or a session override.

    None means explicitly disable credentials at this level. To revert to
    inheritance, call reset_git_credential_selection instead.
    """
    if alias is not None:
        _token_key(scope, alias)
    name = _selection_key(scope, level)
    _store(store).set(
        Credential(
            name=name,
            kind=CredentialKind.OTHER,
            secret=alias if alias is not None else _SELECTION_NONE,
            metadata={
                "purpose": _SELECTION_PURPOSE,
                "disabled": "true" if alias is None else "false",
            },
        )
    )


def reset_git_credential_selection(
    scope: TrustedSandboxScope,
    level: str,
    *,
    store: CredentialStore | None = None,
) -> bool:
    """Remove an override to resume inheritance (or remove user default)."""
    return _store(store).delete(_selection_key(scope, level))


def _selected_alias(store: CredentialStore, scope: TrustedSandboxScope, level: str):
    entry = store.get(_selection_key(scope, level))
    if entry is None:
        return False, None
    if (
        entry.kind != CredentialKind.OTHER
        or entry.metadata.get("purpose") != _SELECTION_PURPOSE
    ):
        raise PermissionError("invalid Git credential selection")
    if entry.metadata.get("disabled") == "true":
        if entry.secret != _SELECTION_NONE:
            raise PermissionError("invalid Git credential disable marker")
        return True, None
    if entry.metadata.get("disabled") != "false":
        raise PermissionError("invalid Git credential selection metadata")
    _token_key(scope, entry.secret)
    return True, entry.secret


def effective_git_credential_alias(
    scope: TrustedSandboxScope,
    *,
    store: CredentialStore | None = None,
) -> str | None:
    """Return only a *reference*, not the token; session wins over user."""
    credentials = _store(store)
    has_session, alias = _selected_alias(credentials, scope, "session")
    if has_session:
        return alias
    _, alias = _selected_alias(credentials, scope, "user")
    return alias


def resolve_git_https_token_for_host(
    scope: TrustedSandboxScope,
    *,
    store: CredentialStore | None = None,
) -> str | None:
    """Broker-only resolver. Never return this value to a model or MXC tool.

    Caller must already have verified the scope's live authorization, target
    remote and operation. This function does not perform a Git connection.
    """
    credentials = _store(store)
    alias = effective_git_credential_alias(scope, store=credentials)
    if alias is None:
        return None
    entry = credentials.get(_token_key(scope, alias))
    if entry is None:
        raise PermissionError("selected Git credential is not available")
    if (
        entry.kind != CredentialKind.OTHER
        or entry.metadata.get("purpose") != _TOKEN_PURPOSE
        or not entry.secret
    ):
        raise PermissionError("selected Git credential has invalid metadata")
    if entry.expires_at is not None and entry.expires_at <= int(time.time()):
        raise PermissionError("selected Git credential has expired")
    return entry.secret
