from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ._matter_history import clear_history, history_count, query_history
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False
STATUS_LABEL = "tool:matter_state_history"

_DEFAULT_OUTPUT_FORMAT = "json"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_state_history",
        "description": _(
            "tool.description",
            default="Query Matter device state change history.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dev": {
                    "type": "string",
                    "description": _(
                        "param.dev.description",
                        default=("Device ID (optional, omit for all)."),
                    ),
                },
                "attribute": {
                    "type": "string",
                    "description": _(
                        "param.attribute.description",
                        default=("Attribute name filter (optional)."),
                    ),
                },
                "since": {
                    "type": "string",
                    "description": _(
                        "param.since.description",
                        default=("Start time ISO8601 (optional)."),
                    ),
                },
                "until": {
                    "type": "string",
                    "description": _(
                        "param.until.description",
                        default=("End time ISO8601 (optional)."),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 10000,
                    "description": _(
                        "param.limit.description",
                        default=("Max entries (default 100, max 10000)."),
                    ),
                },
                "clear": {
                    "type": "boolean",
                    "description": _(
                        "param.clear.description",
                        default=("If true, clear all history."),
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": _DEFAULT_OUTPUT_FORMAT,
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
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"
    if result.get("cleared"):
        return f"State history cleared. Removed {result['cleared']} entries."
    items = result.get("items", [])
    lines = [
        f"Matter state history: {len(items)} entries (total: {result.get('total', 0)})",
    ]
    for entry in items[-20:]:  # Show last 20
        dev = entry.get("dev", "?")
        attr = entry.get("attribute", "?")
        old = entry.get("old", "?")
        new = entry.get("new", "?")
        ts = entry.get("ts", "?")
        lines.append(f"  {ts}  {dev}.{attr}: {old} -> {new}")
    if len(items) > 20:
        lines.append(f"  ... ({len(items) - 20} more)")
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or _DEFAULT_OUTPUT_FORMAT).lower()
    do_clear = bool(args.get("clear", False))

    if do_clear:
        cleared = clear_history()
        result = {
            "ok": True,
            "cleared": cleared,
            "total": 0,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if output_format == "text":
            return _format_text(result)
        return json.dumps(result, ensure_ascii=False)

    device_id = args.get("dev")
    attribute = args.get("attribute")
    since = args.get("since")
    until = args.get("until")
    limit = int(args.get("limit", 100))

    items = query_history(
        device_id=str(device_id) if device_id is not None else None,
        attribute=str(attribute) if attribute is not None else None,
        since=str(since) if since is not None else None,
        until=str(until) if until is not None else None,
        limit=limit,
    )

    result = {
        "ok": True,
        "count": len(items),
        "items": items,
        "total": history_count(),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
