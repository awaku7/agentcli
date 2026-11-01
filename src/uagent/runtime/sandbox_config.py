"""Shared, dependency-free sandbox mode configuration helpers."""

from __future__ import annotations

_VALID_SANDBOX_MODES = frozenset({"off", "auto", "mxc"})


def resolve_sandbox_mode(cli_override: str | None, env_value: str | None) -> str:
    """Resolve CLI-over-environment configuration and reject unknown modes."""
    value = cli_override if cli_override is not None else (env_value or "off")
    mode = str(value).strip().lower()
    if mode not in _VALID_SANDBOX_MODES:
        raise ValueError("UAGENT_SANDBOX_MODE must be off, auto, or mxc")
    return mode


def sandbox_startup_label(enabled: bool) -> str:
    """Translate the process-level Sandbox state, not worker activity."""
    from ..i18n import _

    return _("Sandbox: %(state)s") % {"state": "ON" if enabled else "OFF"}
