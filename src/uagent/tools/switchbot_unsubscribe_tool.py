from __future__ import annotations

import json
from typing import Any

from .switchbot_shared import list_subscriptions, unsubscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:switchbot_unsubscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "switchbot_unsubscribe",
        "description": _(
            "tool.description",
            default=(
                "Cancel a SwitchBot subscription by subscription_id, "
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
                "subscription_id": {
                    "type": "string",
                    "description": _(
                        "param.subscription_id.description",
                        default="Subscription ID to cancel (required for action=unsubscribe).",
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
        return _("msg.no_subscriptions", default="No active SwitchBot subscriptions.")
    lines = [
        _(
            "msg.header",
            default="Active SwitchBot subscriptions ({count}):",
            count=len(subs),
        )
    ]
    for s in subs:
        label = s.get("label") or s.get("device_id", "?")
        lines.append(
            f"  [{s.get('subscription_id')}] {label} (interval={s.get('interval')}s)"
        )
    return "\n".join(lines).strip()


def _format_unsub(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.unsubscribed", default="SwitchBot subscription {id} cancelled."
    ).format(id=payload.get("subscription_id", "?"))


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "unsubscribe").strip().lower()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if action == "list":
        result = list_subscriptions()
        if output_format == "text":
            return _format_list(result)
        return json.dumps(result, ensure_ascii=False)

    sub_id = str(args.get("subscription_id") or "").strip()
    if not sub_id:
        err = _(
            "err.id_required",
            default="subscription_id is required for action=unsubscribe.",
        )
        payload = {"ok": False, "error": err}
        return (
            f"Error: {err}"
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    result = unsubscribe(sub_id)
    if output_format == "text":
        return _format_unsub(result)
    return json.dumps(result, ensure_ascii=False)
