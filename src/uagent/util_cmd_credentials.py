from __future__ import annotations

import getpass
import hashlib
import json
import sys
from typing import Any

from .auth import Credential, CredentialKind, get_default_credential_store
from .util_common import CommandResult


def _parse_kind(raw: str) -> CredentialKind:
    value = (raw or "api_key").strip().lower().replace("-", "_")
    try:
        return CredentialKind(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in CredentialKind)
        raise ValueError(f"invalid credential kind; choose one of: {choices}") from exc


def _ask_user(core: Any, message: str, *, password: bool = False) -> str | None:
    from . import tools

    result = tools.run_tool("human_ask", {"message": message, "is_password": password})
    try:
        payload = result if isinstance(result, dict) else json.loads(result)
    except (TypeError, json.JSONDecodeError):
        return None
    reply = payload.get("user_reply") if isinstance(payload, dict) else None
    return str(reply) if reply is not None else None


def _handle_git_credential_command(
    args: list[str], *, core: Any, store: Any
) -> CommandResult:
    """Configure a local CLI Git host without exposing a secret in arguments."""
    from .runtime.execution_broker import TrustedSandboxScope, current_scope
    from .runtime.sandbox_git_credentials import (
        _selected_alias,
        effective_git_credential_alias,
        remove_git_https_token,
        reset_git_credential_selection,
        save_git_https_token,
        select_git_credential,
        selected_git_https_host_for_scope,
    )
    from .runtime.sandbox_git_http_broker import validate_git_host

    scope = current_scope() or getattr(core, "_sandbox_scope", None)
    if not isinstance(scope, TrustedSandboxScope) or scope.deployment_id != "cli":
        print("Git setup requires an active local CLI Sandbox session.")
        return CommandResult()

    if not args or args == ["status"]:
        try:
            host = selected_git_https_host_for_scope(scope, store=store)
        except (PermissionError, ValueError) as exc:
            print(f"Git credential unavailable: {exc}")
            return CommandResult()
        print(f"Git HTTPS host: {host or 'not configured'}")
        return CommandResult()

    if args == ["remove"]:
        has_session, session_alias = _selected_alias(store, scope, "session")
        level = "session" if has_session else "user"
        alias = (
            session_alias
            if has_session
            else effective_git_credential_alias(scope, store=store)
        )
        if alias is None:
            print("No Git credential is selected.")
            return CommandResult()
        if not sys.stdin.isatty():
            print("Git credential removal requires an interactive terminal.")
            return CommandResult()
        try:
            answer = input("Remove the selected Git credential? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() not in {"y", "yes"}:
            print("Git credential removal cancelled.")
            return CommandResult()
        remove_git_https_token(scope, alias, store=store)
        reset_git_credential_selection(scope, level, store=store)
        print("Selected Git credential revoked.")
        return CommandResult()

    if len(args) != 1:
        print("Usage: :credential git [HOST|status|remove]")
        return CommandResult()
    try:
        host = validate_git_host(args[0])
    except (TypeError, ValueError) as exc:
        print(f"Invalid Git host: {exc}")
        return CommandResult()
    if not sys.stdin.isatty():
        print("Git credential setup requires an interactive terminal.")
        return CommandResult()

    try:
        secret = getpass.getpass(f"Git HTTPS token for {host}: ")
    except (EOFError, KeyboardInterrupt, OSError):
        secret = ""
    if not secret:
        print("Git credential setup cancelled.")
        return CommandResult()

    # Hostname is the alias when it fits; long hostnames use a stable digest.
    alias = host if len(host) <= 64 else hashlib.sha256(host.encode()).hexdigest()
    try:
        save_git_https_token(scope, alias, secret, store=store, remote_host=host)
        select_git_credential(scope, "user", alias, store=store)
        active = effective_git_credential_alias(scope, store=store)
    except (PermissionError, ValueError) as exc:
        print(f"Git credential setup failed: {exc}")
        return CommandResult()
    print(f"Git HTTPS credential configured for {host} (user default).")
    if active != alias:
        print("This session has a separate override; it remains unchanged.")
    return CommandResult()


def handle_credential_command(arg: str, *, core: Any, tr) -> CommandResult:
    parts = (arg or "").split()
    sub = parts[0].lower() if parts else "help"
    store = get_default_credential_store()

    if sub == "git":
        return _handle_git_credential_command(parts[1:], core=core, store=store)

    if sub in {"help", "h", "?"}:
        print(tr("Usage: :credential [get|set|remove|list] NAME"))
        print(tr("set accepts an optional kind after NAME (default: api_key)."))
        print("Sandbox Git: :credential git [HOST|status|remove]")
        return CommandResult()

    if sub == "list":
        list_names = getattr(store, "list_names", None)
        if not callable(list_names):
            print(tr("The current credential backend cannot enumerate names."))
            return CommandResult()
        for name in list_names():
            print(name)
        return CommandResult()

    if len(parts) < 2:
        print(tr("Usage: :credential get|set|remove NAME"))
        return CommandResult()

    name = parts[1]
    if sub == "get":
        credential = store.get(name)
        if credential is None:
            print(tr("Credential not found: %(name)s") % {"name": name})
            return CommandResult()
        print(f"name: {credential.name}")
        print(f"kind: {credential.kind.value}")
        print(f"expires_at: {credential.expires_at}")
        print(f"metadata: {credential.metadata}")
        return CommandResult()

    if sub == "set":
        kind = _parse_kind(parts[2] if len(parts) >= 3 else "api_key")
        secret = _ask_user(core, tr("Enter credential secret:"), password=True)
        if not secret:
            print(tr("Credential update cancelled."))
            return CommandResult()
        store.set(Credential(name=name, kind=kind, secret=secret))
        print(tr("Credential saved: %(name)s") % {"name": name})
        return CommandResult()

    if sub in {"remove", "delete"}:
        answer = _ask_user(
            core,
            tr("Remove credential %(name)s? Enter y to proceed, or c to cancel.")
            % {"name": name},
        )
        if (answer or "").strip().lower() not in {"y", "yes"}:
            print(tr("Credential removal cancelled."))
            return CommandResult()
        print(
            tr("Credential removed: %(name)s") % {"name": name}
            if store.delete(name)
            else tr("Credential not found: %(name)s") % {"name": name}
        )
        return CommandResult()

    print(tr("Usage: :credential [get|set|remove|list] NAME"))
    return CommandResult()
