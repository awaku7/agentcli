"""Shared utilities for Matter tools.

Consolidates error payload construction, recovery hints, and warnings
to ensure consistent error responses across all matter_* tools.
"""

from __future__ import annotations

from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# ---------------------------------------------------------------------------
# Recovery hints — mapping from error code to user-facing suggestion
# ---------------------------------------------------------------------------
_RECOVERY_HINTS: dict[str, str] = {
    "config_missing": _(
        "hint.config_missing",
        default="Set the corresponding UAGENT_MATTER_*_JSON environment variable "
        "or UAGENT_MATTER_*_FILE to point to a valid JSON configuration file.",
    ),
    "invalid_config": _(
        "hint.invalid_config",
        default="Check that the JSON value set in UAGENT_MATTER_*_JSON or the file "
        "pointed to by UAGENT_MATTER_*_FILE is valid JSON.",
    ),
    "not_found": _(
        "hint.not_found",
        default="Verify the device/controller/bridge ID using matter_controller_list "
        "or matter_bridge_list to see available IDs.",
    ),
    "ambiguous_target": _(
        "hint.ambiguous_target",
        default="Specify a ctrl or bridge parameter to narrow the search.",
    ),
    "invalid_argument": _(
        "hint.invalid_argument",
        default="Check the required parameters for this tool. Use :help for details.",
    ),
    "unsupported_action": _(
        "hint.unsupported_action",
        default="This device type does not support the requested action. "
        "Use matter_device_status to check the device type, then choose "
        "a compatible action (on/off for lights/switches, lock/unlock for locks, etc.).",
    ),
    "request_failed": _(
        "hint.request_failed",
        default="An unexpected error occurred. Check the tool arguments and try again.",
    ),
}


def error_payload(
    code: str,
    message: str,
    extra: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    extra_top: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standardized error payload with recovery_hint.

    Args:
        code: Error code string (e.g. 'not_found').
        message: Human-readable error message.
        extra: Extra fields to merge into the error dict.
        warnings: Optional list of warning strings.
        extra_top: Extra fields to add at the top level (siblings of 'error').
    """
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "recovery_hint": _RECOVERY_HINTS.get(code, ""),
        },
    }
    if extra:
        payload["error"].update(extra)
    if warnings:
        payload["warnings"] = warnings
    if extra_top:
        payload.update(extra_top)
    return payload


def ok_payload(
    data: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap a successful result dict, optionally adding warnings."""
    payload: dict[str, Any] = {"ok": True, **data}
    if warnings:
        payload["warnings"] = warnings
    return payload


# ---------------------------------------------------------------------------
# Warning collector helper
# ---------------------------------------------------------------------------


class WarningCollector:
    """Collect non-fatal warnings during tool execution.

    Usage:
        warnings = WarningCollector()
        warnings.add("Something is off but we can continue.")
        result = ok_payload({...}, warnings=warnings.get())
    """

    def __init__(self) -> None:
        self._items: list[str] = []

    def add(self, message: str) -> None:
        self._items.append(message)

    def get(self) -> list[str]:
        return list(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)
