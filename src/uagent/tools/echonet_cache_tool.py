from __future__ import annotations

import json
from typing import Any

from .echonet_cache_shared import cache_clear, cache_snapshot
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_cache"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "echonet_cache",
        "description": _(
            "tool.description",
            default="Inspect or clear the shared ECHONET Lite cache.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["snapshot", "clear"],
                    "default": "snapshot",
                    "description": _(
                        "param.action.description",
                        default="Cache action to perform: snapshot or clear.",
                    ),
                },
                "namespace": {
                    "type": "string",
                    "description": _(
                        "param.namespace.description",
                        default=("Cache namespace (omit for all)."),
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
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def _format_snapshot(payload: dict[str, Any]) -> str:
    lines = [
        _(
            "msg.snapshot",
            default="ECHONET cache snapshot: {count} item(s).",
            count=payload.get("count", 0),
        )
    ]
    namespaces = payload.get("namespaces") or {}
    if namespaces:
        parts = [f"{name}={count}" for name, count in sorted(namespaces.items())]
        lines.append(f"Namespaces: {', '.join(parts)}")
    items = payload.get("items") or []
    if not items:
        lines.append(
            _(
                "msg.no_items",
                default="No cached entries are present.",
            )
        )
        return "\n".join(lines).strip()
    for idx, item in enumerate(items, 1):
        lines.append(f"[{idx}] {item.get('namespace') or '-'}")
        lines.append(f"  key: {item.get('key') or '-'}")
        lines.append(f"  age_ms: {item.get('age_ms')}")
        if item.get("created_at"):
            lines.append(f"  created_at: {item.get('created_at')}")
        lines.append("")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "snapshot").strip().lower()
    namespace = args.get("namespace")
    output_format = str(args.get("fmt") or "json").strip().lower()

    if action == "snapshot":
        payload = cache_snapshot()
        payload["action"] = "snapshot"
        if output_format == "text":
            return _format_snapshot(payload)
        return json.dumps(payload, ensure_ascii=False)

    if action == "clear":
        removed = cache_clear(
            str(namespace).strip()
            if namespace is not None and str(namespace).strip()
            else None
        )
        payload = {
            "ok": True,
            "action": "clear",
            "namespace": (
                str(namespace).strip()
                if namespace is not None and str(namespace).strip()
                else None
            ),
            "removed": removed,
        }
        if output_format == "text":
            scope = payload["namespace"] or "all namespaces"
            return _(
                "msg.cleared",
                default="Cleared {removed} cached entries from {scope}.",
                removed=removed,
                scope=scope,
            )
        return json.dumps(payload, ensure_ascii=False)

    payload = {
        "ok": False,
        "error": {
            "code": "invalid_argument",
            "message": _(
                "err.invalid_action",
                default="Error: action must be 'snapshot' or 'clear'.",
            ),
        },
    }
    if output_format == "text":
        return payload["error"]["message"]
    return json.dumps(payload, ensure_ascii=False)
