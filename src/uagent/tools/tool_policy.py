"""Side-effect policy for tool scheduling and confirmation."""

from __future__ import annotations

import json
import os

from ..i18n import _
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SideEffect(str, Enum):
    READ_ONLY = "read_only"
    IDEMPOTENT_WRITE = "idempotent_write"
    EXTERNAL_SEND = "external_send"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolPolicy:
    side_effect: SideEffect
    parallel_safe: bool = False
    resource_key: str | None = None
    requires_confirmation: bool = False


_READ_ONLY = {
    "calculator",
    "file_exists",
    "file_grep",
    "file_hash",
    "file_type",
    "get_env",
    "get_long_memory",
    "get_shared_memory",
    "get_workdir",
    "read_file",
    "search_files",
    "search_web",
    "fetch_url",
    "http_request",
    "db_query",
    "get_current_time",
    "get_weather_wttr",
    "zipcode_check",
    "code_map",
    "coverage_report",
    "security_scan",
}
_EXTERNAL_SEND = {
    "gmail_send",
    "discord_channel_chat",
    "bluesky",
    "teams_webhook_post",
    "mqtt_publish",
    "pybitchat_send",
    "packet_send",
    "ucp_checkout",
    "ucp_ap2",
}
_DESTRUCTIVE = {
    "delete_file",
    "rename_path",
    "binary_edit",
}


def _resource_key(tool_name: str, args: dict[str, Any]) -> str | None:
    for field in (
        "resource",
        "dev",
        "device_id",
        "path",
        "file_path",
        "url",
        "host",
        "ip",
    ):
        value = args.get(field)
        if value not in (None, ""):
            return chr(58).join((tool_name, field, str(value)))
    return None


def policy_for(tool_name: str, args: dict[str, Any] | None = None) -> ToolPolicy:
    args = args or {}

    # A preview does not modify files. Treat both single-file and
    # replace_all_in_files previews as read-only so they can be inspected
    # without requiring a destructive-operation confirmation.
    if tool_name == "replace_in_file":
        preview = args.get("preview", True)
        if isinstance(preview, str):
            preview = preview.strip().lower() not in {"0", "false", "no", "off"}
        if bool(preview):
            return ToolPolicy(
                SideEffect.READ_ONLY,
                parallel_safe=True,
                resource_key=_resource_key(tool_name, args),
            )
    if tool_name in _READ_ONLY:
        if tool_name == "http_request":
            method = str(args.get("method") or "GET").upper()
            if method not in {"GET", "HEAD", "OPTIONS"}:
                return ToolPolicy(
                    SideEffect.EXTERNAL_SEND,
                    resource_key=_resource_key(tool_name, args),
                    requires_confirmation=True,
                )
        return ToolPolicy(
            SideEffect.READ_ONLY,
            parallel_safe=True,
            resource_key=_resource_key(tool_name, args),
        )
    if tool_name in _DESTRUCTIVE:
        return ToolPolicy(
            SideEffect.DESTRUCTIVE,
            resource_key=_resource_key(tool_name, args),
            requires_confirmation=True,
        )
    if tool_name in _EXTERNAL_SEND:
        return ToolPolicy(
            SideEffect.EXTERNAL_SEND,
            resource_key=_resource_key(tool_name, args),
            requires_confirmation=True,
        )
    return ToolPolicy(
        SideEffect.IDEMPOTENT_WRITE,
        resource_key=_resource_key(tool_name, args),
        parallel_safe=False,
    )


def default_confirmation_callback(
    tool_name: str, args: dict[str, Any], policy: ToolPolicy
) -> bool:
    """Ask the human for confirmation, with an environment override for automation."""
    value = (os.environ.get("UAGENT_CONFIRM_TOOLS", "") or "").strip().lower()
    if value in {"1", "true", "yes", "on", "allow"}:
        return True

    # Reuse the normal human_ask callback path so CLI/GUI/Web can all confirm
    # side effects interactively instead of treating a missing env var as denial.
    try:
        from .human_ask_tool import run_tool

        result = json.loads(
            run_tool(
                {
                    "message": (
                        _("Allow the side-effecting tool '%(tool)s' to run? Reply yes to continue or no to cancel.")
                        % {"tool": tool_name}
                    ),
                    "is_password": False,
                }
            )
        )
        if result.get("auto_pilot_skipped") or result.get("cancelled"):
            return False
        return str(result.get("user_reply", "")).strip().lower() in {
            "y",
            "yes",
            "\u627f\u8a8d",
            "\u8a31\u53ef",
            "\u306f\u3044",
        }
    except Exception:
        return False


def is_parallel_safe(tool_name: str, args: dict[str, Any] | None = None) -> bool:
    return policy_for(tool_name, args).parallel_safe
