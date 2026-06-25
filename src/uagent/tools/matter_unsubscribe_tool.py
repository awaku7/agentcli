from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ._matter_subscribe import remove_subscription
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:matter_unsubscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_unsubscribe",
        "description": _(
            "tool.description",
            default="Remove a Matter device subscription.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "subscription_id": {
                    "type": "string",
                    "description": _(
                        "param.subscription_id.description",
                        default="Subscription ID to remove.",
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description",
                        default="Format: json or text.",
                    ),
                },
            },
            "required": ["subscription_id"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    sub_id = str(args.get("subscription_id") or "").strip()

    if not sub_id:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.subscription_id_required",
                    default="Subscription ID is required.",
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    found = remove_subscription(sub_id)
    if not found:
        payload = {
            "ok": False,
            "error": {
                "code": "not_found",
                "message": _(
                    "err.subscription_not_found", default="Subscription not found: {id}"
                ).format(id=sub_id),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    result = {
        "ok": True,
        "removed": sub_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if output_format == "text":
        return f"Subscription removed: {sub_id}"
    return json.dumps(result, ensure_ascii=False)


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"
    return f"Subscription removed: {result.get('removed', '?')}"
