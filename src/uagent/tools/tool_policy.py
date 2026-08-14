"""Side-effect policy for tool scheduling and confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
import os


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
    "replace_in_file",
    "binary_edit",
    "git_ops",
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
    """Conservative host callback; explicit allow is required for side effects."""
    value = (os.environ.get("UAGENT_CONFIRM_TOOLS", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on", "allow"}


def is_parallel_safe(tool_name: str, args: dict[str, Any] | None = None) -> bool:
    return policy_for(tool_name, args).parallel_safe
