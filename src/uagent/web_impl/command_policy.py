"""Fail-closed command admission for Remote Web rooms."""

from __future__ import annotations

_REMOTE_WEB_SAFE_COMMANDS = frozenset(
    {
        "help",
        "h",
        "?",
        "r",
        "reasoning",
        "v",
        "verbosity",
    }
)

REMOTE_WEB_COMMAND_DENIED = (
    "Remote Web commands are restricted to help and mode changes until a "
    "Sandbox command backend is available."
)


def web_command_denial(
    command_text: str, *, execution_profile: str | None
) -> str | None:
    """Return a denial reason unless a Remote Web command is explicitly safe.

    This admission check is deliberately independent of ``handle_command`` and
    dynamic command registration. Unknown and plugin-namespaced commands must
    never reach a Host command dispatcher from Remote Web.
    """
    if execution_profile == "local_trusted":
        return None

    body = str(command_text or "").strip().lstrip(":").strip()
    if not body:
        return REMOTE_WEB_COMMAND_DENIED

    command = body.split(maxsplit=1)[0].lower()
    if ":" in command or command not in _REMOTE_WEB_SAFE_COMMANDS:
        return REMOTE_WEB_COMMAND_DENIED
    return None
