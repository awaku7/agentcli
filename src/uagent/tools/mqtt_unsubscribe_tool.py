from __future__ import annotations

import json
from typing import Any

from .mqtt_shared import disconnect
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:mqtt_unsubscribe"

from .mqtt_subscribe_tool import _SUBSCRIPTIONS, _SUBS_LOCK


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "mqtt_unsubscribe",
        "description": _(
            "tool.description",
            default=(
                "Cancel an MQTT subscription by subscription_id, "
                "or list active subscriptions."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string", "enum": ["unsubscribe", "list"], "default": "unsubscribe",
                    "description": _("param.action.description", default="Action: 'unsubscribe' or 'list'."),
                },
                "subscription_id": {
                    "type": "string",
                    "description": _("param.subscription_id.description", default="Subscription ID to cancel."),
                },
                "fmt": {
                    "type": "string", "enum": ["json", "text"], "default": "json",
                    "description": _("param.fmt.description", default="Format: json or text."),
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
        return _("msg.no_subscriptions", default="No active MQTT subscriptions.")
    lines = [_("msg.header", default="Active MQTT subscriptions ({count}):", count=len(subs))]
    for s in subs:
        lines.append(f"  [{s.get('subscription_id')}] {s.get('label', '?')} @ {s.get('host')} topic={s.get('topic')}")
    return "\n".join(lines).strip()


def _format_unsub(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _("msg.unsubscribed", default="MQTT subscription {id} cancelled.", id=payload.get("subscription_id", "?"))


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "unsubscribe").strip().lower()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if action == "list":
        with _SUBS_LOCK:
            subs = [{"subscription_id": sid, "host": s.get("host"), "topic": s.get("topic"),
                     "label": s.get("label"), "status": s.get("status")}
                    for sid, s in _SUBSCRIPTIONS.items()]
        result = {"ok": True, "count": len(subs), "subscriptions": subs}
        return _format_list(result) if output_format == "text" else json.dumps(result, ensure_ascii=False)

    sub_id = str(args.get("subscription_id") or "").strip()
    if not sub_id:
        err = _("err.id_required", default="subscription_id is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    with _SUBS_LOCK:
        info = _SUBSCRIPTIONS.pop(sub_id, None)
    if not info:
        err = f"subscription_id '{sub_id}' not found"
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    client = info.get("client")
    if client:
        disconnect(client)

    result = {"ok": True, "subscription_id": sub_id}
    return _format_unsub(result) if output_format == "text" else json.dumps(result, ensure_ascii=False)
