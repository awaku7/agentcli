"""Standard user attributes from the server-bound actor, never message input."""

from __future__ import annotations

import getpass
import socket

from ..identity_context import TurnContext, get_current_identity_context
from .settings import ObservabilitySettings


def _text(value: object) -> str | None:
    if type(value) is not str or not 1 <= len(value) <= 512:
        return None
    if any(
        ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
        for char in value
    ):
        return None
    return value if value.strip() else None


def user_attributes(
    turn: TurnContext, settings: ObservabilitySettings
) -> dict[str, str]:
    """Identify authenticated actors; pseudonymous mode never exports raw users.

    Local CLI/GUI actors use the OS account, scoped to its host. A remote turn
    must never fall back to the account running the Web/A2A server.
    """
    if (
        not settings.enabled
        or settings.pseudonymous_correlation
        or not turn.authenticated
    ):
        return {}
    identity = get_current_identity_context()
    if turn.authn_kind == "local" and turn.entry_point in {"cli", "gui"}:
        try:
            name = _text(getpass.getuser())
            host = _text(socket.gethostname())
        except Exception:
            return {}
        if not name or not host:
            return {}
        identifier = _text(f"local:{host}:{name}")
        return {"user.id": identifier, "user.name": name} if identifier else {}
    identifier = _text(turn.principal_id)
    if not identifier:
        return {}
    attributes = {"user.id": identifier}
    if (
        identity is not None
        and identity.authenticated
        and identity.principal_id == turn.principal_id
        and identity.authn_kind == turn.authn_kind
    ):
        name = _text(identity.username)
        if name:
            attributes["user.name"] = name
    return attributes
