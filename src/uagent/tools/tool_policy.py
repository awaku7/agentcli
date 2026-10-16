"""Side-effect policy for tool scheduling and confirmation."""

from __future__ import annotations

import json
import os
import threading
import unicodedata

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
    "artifact_info",
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

# Private dispatcher-to-runner signal: the common tool policy has already
# obtained user approval, so a tool with a secondary safety check can avoid
# asking the same question again. This is stripped from model-supplied args at
# the dispatch boundary and only set after a successful confirmation callback.
CONFIRMATION_GRANTED_ARG = "_uagent_policy_confirmation_granted"
CONFIRMATION_GRANTED_TOKEN = object()

# Explicit "all" grants are tied to an authenticated Room/Session/Task.
# An unbound tool call can receive one-time approval but cannot persist "all".
_ALLOW_ALL_TOOLS: set[tuple[tuple[str, ...], str]] = set()
_ALLOW_ALL_LOCK = threading.RLock()

_CONFIRM_REPLY_DENY = "deny"
_CONFIRM_REPLY_YES = "yes"
_CONFIRM_REPLY_ALL = "all"


def _absolute_confirmation_required(tool_name: str, args: dict[str, Any]) -> bool:
    """A configured absconfirm cannot be bypassed by a previous 'all' grant."""
    from .. import core
    from .enterprise_policy import get_enterprise_policy

    enterprise = get_enterprise_policy()
    injected = os.environ.get("UAGENT_INJECT_MODE") == "1"
    auto_pilot = bool(getattr(core, "auto_pilot_active", False))
    return (injected and enterprise.inject_requires_confirmation(tool_name, args)) or (
        auto_pilot and enterprise.auto_pilot_requires_confirmation(tool_name, args)
    )


def _confirmation_scope_key() -> tuple[str, ...] | None:
    from ..runtime.identity_context import get_current_turn_context

    turn = get_current_turn_context()
    if turn is not None:
        boundary = turn.room_id if turn.entry_point == "web" else turn.session_id
        if not boundary:
            return None
        return (
            turn.entry_point,
            turn.principal_id,
            turn.project_id,
            boundary,
        )

    from ..runtime.execution_broker import current_scope

    scope = current_scope()
    if scope is not None:
        return (
            scope.scope_kind,
            scope.deployment_id,
            scope.principal_id,
            scope.project_id,
            scope.scope_id,
        )

    # Legacy trusted local CLI/GUI without a TurnContext.
    from .. import core

    session_id = str(getattr(core, "session_id", "") or "").strip()
    if session_id:
        return ("local", session_id)
    return None


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


def _confirmation_reply_kind(raw_reply: Any) -> str:
    """Classify only exact, explicit replies in the configured UI language."""

    def normalize(value: Any) -> str:
        return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()

    reply = normalize(raw_reply)
    if not reply:
        return _CONFIRM_REPLY_DENY

    if reply in {
        normalize(item)
        for item in ("n", "no", "c", "cancel", _tool_("confirm.reply_no", default="no"))
    }:
        return _CONFIRM_REPLY_DENY
    if reply in {
        normalize(item)
        for item in (
            "all",
            "a",
            "all yes",
            "yes to all",
            "\u3059\u3079\u3066\u306f\u3044",
            "\u5168\u3066\u306f\u3044",
            _tool_("confirm.reply_all", default="all"),
        )
    }:
        return _CONFIRM_REPLY_ALL
    if reply in {
        normalize(item)
        for item in (
            "y",
            "yes",
            "\u627f\u8a8d",
            "\u8a31\u53ef",
            "\u306f\u3044",
            _tool_("confirm.reply_yes", default="yes"),
        )
    }:
        return _CONFIRM_REPLY_YES
    return _CONFIRM_REPLY_DENY


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


def _delete_is_preview(args: dict[str, Any]) -> bool:
    """Match delete_file's actual dry_run defaults, not its schema default."""
    if "dry_run" in args:
        return args["dry_run"] is True
    raw = args.get("filename")
    if raw is None:
        raw = args.get("path")
    items = [raw] if isinstance(raw, str) else raw
    if not isinstance(items, list):
        return False
    return any(
        isinstance(item, str) and any(char in item for char in ("*", "?", "["))
        for item in items
    )


def policy_for(tool_name: str, args: dict[str, Any] | None = None) -> ToolPolicy:
    args = args or {}

    # Preview returns matched paths without deleting them. Keep real deletion,
    # including caller-provided confirmed=True, subject to host confirmation.
    if tool_name == "delete_file" and _delete_is_preview(args):
        return ToolPolicy(
            SideEffect.READ_ONLY,
            parallel_safe=True,
            resource_key=_resource_key(tool_name, args),
        )

    # Only actual packet sends need confirmation. A preview never transmits.
    if tool_name == "packet_send" and bool(args.get("dry_run", True)):
        return ToolPolicy(
            SideEffect.READ_ONLY,
            parallel_safe=True,
            resource_key=_resource_key(tool_name, args),
        )

    # Elevation for raw packet probes is a separate destructive privilege path.
    # Keep ordinary socket probes on their existing policy.
    if tool_name == "packet_probe":
        action = str(args.get("action", "tcp_connect")).lower()
        if (
            action in {"tcp_syn", "icmp", "arp"}
            and bool(args.get("allow_elevation", False))
            and not bool(args.get("dry_run", False))
        ):
            return ToolPolicy(
                SideEffect.DESTRUCTIVE,
                resource_key=_resource_key(tool_name, args),
                requires_confirmation=True,
            )

    # ``lint_format`` is read-only in check mode, but ruff/black (and the
    # other formatters) can overwrite source files in fix mode.  Classify
    # that mutation at the common dispatcher layer, just like
    # ``delete_file`` and ``binary_edit``, so every host UI gets the same
    # confirmation behavior before the tool runner starts.
    if tool_name == "lint_format":
        mode = str(args.get("mode") or "check").strip().lower()
        if mode == "fix":
            return ToolPolicy(
                SideEffect.DESTRUCTIVE,
                resource_key=_resource_key(tool_name, args),
                requires_confirmation=True,
            )
        return ToolPolicy(
            SideEffect.READ_ONLY,
            parallel_safe=True,
            resource_key=_resource_key(tool_name, args),
        )

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
    if tool_name == "artifact_export" and bool(args.get("overwrite", False)):
        return ToolPolicy(
            SideEffect.DESTRUCTIVE,
            resource_key=_resource_key(tool_name, args),
            requires_confirmation=True,
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
    scope_key = _confirmation_scope_key()
    try:
        absconfirm = _absolute_confirmation_required(tool_name, args)
    except Exception:
        absconfirm = True
    with _ALLOW_ALL_LOCK:
        if (
            not absconfirm
            and scope_key is not None
            and (scope_key, tool_name) in _ALLOW_ALL_TOOLS
        ):
            return True

    value = (os.environ.get("UAGENT_CONFIRM_TOOLS", "") or "").strip().lower()
    if not absconfirm and value in {"1", "true", "yes", "on", "allow"}:
        return True

    # Show the locally translated 'all' answer in CLI, GUI and Web alike.
    # For absconfirm or unscoped runs, never advertise a persistent grant.
    allow_all = scope_key is not None and not absconfirm
    confirmation_message = _tool_(
        "confirm.side_effecting_tool",
        default=(
            "Allow the side-effecting tool '%(tool)s' to run? "
            "Reply yes to continue or no to cancel."
        ),
        tool=tool_name,
    )
    # Keep masked arguments visible without invalidating the 38-language
    # translations, which only interpolate %(tool)s.
    confirmation_message += "\n" + _confirmation_args(args)
    if allow_all:
        confirmation_message += (
            "\n"
            + _tool_(
                "ui.all_yes",
                default="  - Type 'all' to allow this tool for the rest of the session\n",
            ).strip()
        )

    # Web human_ask is routed through its authenticated Room UI wrapper.
    # Calling human_ask_tool directly would wait on an unused CLI queue.
    try:
        from .. import core
        from ..runtime.identity_context import get_current_turn_context

        turn = get_current_turn_context()
        web_turn = turn is not None and turn.entry_point == "web"
        if getattr(core, "_is_web", False) and not web_turn:
            return False

        request = {
            "message": confirmation_message,
            "is_password": False,
            "confirmation": allow_all,
            "_confirmation_hint_in_message": allow_all,
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
        if web_turn:
            from . import run_tool as frontend_run_tool

            result = json.loads(frontend_run_tool("human_ask", request))
        else:
            from .human_ask_tool import run_tool as human_ask

            result = json.loads(human_ask(request))
        if result.get("auto_pilot_skipped") or result.get("cancelled"):
            return False
        reply_kind = _confirmation_reply_kind(result.get("user_reply", ""))
        if reply_kind == "all":
            if allow_all:
                with _ALLOW_ALL_LOCK:
                    _ALLOW_ALL_TOOLS.add((scope_key, tool_name))
            return True
        return reply_kind == "yes"
    except Exception:
        return False


def is_parallel_safe(tool_name: str, args: dict[str, Any] | None = None) -> bool:
    return policy_for(tool_name, args).parallel_safe
