from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ._matter_subscribe import list_subscriptions
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:matter_subscription_list"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_subscription_list",
        "description": _(
            "tool.description",
            default="List active Matter device subscriptions.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
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
            "additionalProperties": False,
        },
    },
}


def _format_text(result: dict[str, Any]) -> str:
    items = result.get("items", [])
    if not items:
        return "No active subscriptions."
    lines = [f"Active subscriptions: {result.get('count', 0)}"]
    for sub in items:
        lines.append(
            f"  [{sub.get('subscription_id')}] {sub.get('dev')} "
            f"(remaining: {sub.get('remaining_seconds')}s)"
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    items = list_subscriptions()
    result = {
        "ok": True,
        "count": len(items),
        "items": items,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
