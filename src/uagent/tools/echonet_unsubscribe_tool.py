from __future__ import annotations

import json
from typing import Any

from .echonet_shared import list_subscriptions, unsubscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_unsubscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "echonet_unsubscribe",
        "description": _(
            "tool.description",
            default=(
                "Cancel an ECHONET Lite INF subscription by listener_id, "
                "or list active subscriptions."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["unsubscribe", "list"],
                    "default": "unsubscribe",
                    "description": _(
                        "param.action.description",
                        default="Action: 'unsubscribe' (default) or 'list'.",
                    ),
                },
                "listener_id": {
                    "type": "string",
                    "description": _(
                        "param.listener_id.description",
                        default="Listener ID to unsubscribe (required for action=unsubscribe).",
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
            "additionalProperties": False,
        },
    },
}


def _format_list(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    subs = payload.get("subscriptions") or []
    if not subs:
        return _(
            "msg.no_subscriptions", default="No active ECHONET Lite subscriptions."
        )
    lines = [
        _(
            "msg.header",
            default="Active ECHONET Lite subscriptions ({count}):",
            count=len(subs),
        )
    ]
    for s in subs:
        label = s.get("label") or s.get("ip", "?")
        lines.append(f"  [{s.get('listener_id')}] {label} @ {s.get('ip')}")
    return "\n".join(lines).strip()


def _format_unsub(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.unsubscribed", default="ECHONET Lite subscription {id} cancelled."
    ).format(id=payload.get("listener_id", "?"))


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "unsubscribe").strip().lower()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if action == "list":
        result = list_subscriptions()
        if output_format == "text":
            return _format_list(result)
        return json.dumps(result, ensure_ascii=False)

    listener_id = str(args.get("listener_id") or "").strip()
    if not listener_id:
        err = _(
            "err.id_required", default="listener_id is required for action=unsubscribe."
        )
        payload = {"ok": False, "error": err}
        return (
            f"Error: {err}"
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    result = unsubscribe(listener_id)
    if output_format == "text":
        return _format_unsub(result)
    return json.dumps(result, ensure_ascii=False)
