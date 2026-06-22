from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ._matter_subscribe import create_subscription
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:matter_subscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_subscribe",
        "description": _(
            "tool.description",
            default="Subscribe to state changes of a Matter device.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dev": {
                    "type": "string",
                    "description": _(
                        "param.dev.description",
                        default="Device ID (required).",
                    ),
                },
                "endpoint": {
                    "type": "string",
                    "description": _(
                        "param.endpoint.description",
                        default=("Endpoint filter (optional)."),
                    ),
                },
                "cluster": {
                    "type": "string",
                    "description": _(
                        "param.cluster.description",
                        default=("Cluster filter (optional)."),
                    ),
                },
                "attribute": {
                    "type": "string",
                    "description": _(
                        "param.attribute.description",
                        default=("Attribute filter (optional)."),
                    ),
                },
                "duration": {
                    "type": "integer",
                    "default": 3600,
                    "description": _(
                        "param.duration.description",
                        default=("Subscription duration in seconds (default 3600)."),
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
            "required": ["device_id"],
            "additionalProperties": False,
        },
    },
}


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"
    sub = result.get("subscription", {})
    return (
        f"Subscribed to Matter device: {sub.get('dev')}\n"
        f"  Subscription ID: {sub.get('subscription_id')}\n"
        f"  Endpoint: {sub.get('endpoint') or 'all'}\n"
        f"  Cluster: {sub.get('cluster') or 'all'}\n"
        f"  Attribute: {sub.get('attribute') or 'all'}\n"
        f"  Duration: {sub.get('duration')}s\n"
        f"  Remaining: {sub.get('remaining_seconds')}s"
    )


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    device_id = str(args.get("dev") or "").strip()

    if not device_id:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _("err.device_id_required", default="Device ID is required."),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    sub = create_subscription(
        device_id=device_id,
        endpoint=str(args.get("endpoint")) if args.get("endpoint") else None,
        cluster=str(args.get("cluster")) if args.get("cluster") else None,
        attribute=str(args.get("attribute")) if args.get("attribute") else None,
        duration=int(args.get("duration", 3600)),
    )

    result = {
        "ok": True,
        "subscription": sub,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
