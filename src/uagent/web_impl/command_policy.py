"""Fail-closed command admission for Remote Web rooms."""

from __future__ import annotations

_SAFE_MODE_COMMANDS = frozenset({"r", "reasoning", "v", "verbosity"})

WEB_COMMAND_DENIED = (
    "Host command execution is disabled in this Web security profile because "
    "no Sandbox command backend is available."
)


def web_command_denial(
    command_text: str,
    *,
    execution_profile: str | None,
    sandbox_enabled: bool = False,
) -> str | None:
    """Return a denial reason unless the command is safe in this profile.

    The legacy Host dispatcher is available only to trusted local Web with
    Sandbox off. Remote and sandbox-enabled Web may use only mode changes; help
    is excluded because its catalog can import Host plugins.
    """
    if execution_profile == "local_trusted" and not sandbox_enabled:
        return None

    body = str(command_text or "").strip().lstrip(":").strip()
    if not body:
        return WEB_COMMAND_DENIED

    command = body.split(maxsplit=1)[0].lower()
    if ":" in command or command not in _SAFE_MODE_COMMANDS:
        return WEB_COMMAND_DENIED
    return None
