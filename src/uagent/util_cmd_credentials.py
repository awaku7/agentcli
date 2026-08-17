from __future__ import annotations

import json
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


def handle_credential_command(arg: str, *, core: Any, tr) -> CommandResult:
    parts = (arg or "").split()
    sub = parts[0].lower() if parts else "help"
    store = get_default_credential_store()

    if sub in {"help", "h", "?"}:
        print(tr("Usage: :credential [get|set|remove|list] NAME"))
        print(tr("set accepts an optional kind after NAME (default: api_key)."))
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
