"""Side-effect policy for tool scheduling and confirmation."""

from __future__ import annotations

import json
import os
import threading

from .i18n_helper import make_tool_translator
from dataclasses import dataclass
from enum import Enum
from typing import Any

_tool_ = make_tool_translator(
    os.path.join(os.path.dirname(__file__), "human_ask_tool.py")
)


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

# Tool names explicitly approved with "all" are scoped to this process/session.
_ALLOW_ALL_TOOLS: set[str] = set()
_ALLOW_ALL_LOCK = threading.RLock()


def _confirmation_args(args: dict[str, Any]) -> str:
    """Render tool arguments for confirmation without exposing credentials."""
    # Share the recursive masker used by tool traces and logs. The old local
    # implementation only inspected top-level keys.
    from ..utils.secret_mask import mask_args

    safe = mask_args(args)
    try:
        rendered = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        rendered = repr(safe)
    return rendered if len(rendered) <= 8000 else rendered[:7997] + "..."


def reset_confirmation_grants() -> None:
    """Clear per-tool "all approved" grants for a new host session."""
    with _ALLOW_ALL_LOCK:
        _ALLOW_ALL_TOOLS.clear()


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
    with _ALLOW_ALL_LOCK:
        if tool_name in _ALLOW_ALL_TOOLS:
            return True

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
                        _tool_(
                            "confirm.side_effecting_tool",
                            default=(
                                "Allow the side-effecting tool '%(tool)s' to run? "
                                " [Arguments: %(args)s]"
                                "Reply yes to continue or no to cancel."
                            ),
                            tool=tool_name,
                            args=_confirmation_args(args),
                        )
                    ),
                    "is_password": False,
                    "confirmation": True,
                    "_auto_pilot_tool": tool_name,
                    "_server_name": args.get("server_name", ""),
                    "_mcp_tool": args.get("tool_name", ""),
                    "_auto_pilot_mcp_key": (
                        f"{args.get('server_name')}:{args.get('tool_name')}"
                        if tool_name == "handle_mcp_v2"
                        and args.get("server_name")
                        and args.get("tool_name")
                        else ""
                    ),
                }
            )
        )
        if result.get("auto_pilot_skipped") or result.get("cancelled"):
            return False
        reply = str(result.get("user_reply", "")).strip().lower()
        if reply in {
            "all",
            "a",
            "all yes",
            "yes to all",
            "\u3059\u3079\u3066\u306f\u3044",
            "\u5168\u3066\u306f\u3044",
        }:
            with _ALLOW_ALL_LOCK:
                _ALLOW_ALL_TOOLS.add(tool_name)
            return True
        return reply in {
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
