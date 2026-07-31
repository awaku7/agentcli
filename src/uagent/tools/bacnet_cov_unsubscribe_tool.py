from __future__ import annotations

import json
from typing import Any

from .bacnet_shared import cov_list, cov_unsubscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:bacnet_cov_unsubscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "bacnet_cov_unsubscribe",
        "description": _(
            "tool.description",
            default=(
                "Cancel a BACnet COV subscription by task_id, or list active subscriptions. "
                "Use 'list' action to see all active subscriptions and their task_ids."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "bacnet cov unsubscribe",
                "bacnet_cov_unsubscribe",
                "bacnet",
                "BACNET",
                "cov",
                "cancel",
                "subscription",
                "task_id",
            ],
        ),
        "x_search_terms_en": [
            "bacnet cov unsubscribe",
            "bacnet_cov_unsubscribe",
            "bacnet",
            "BACNET",
            "cov",
            "cancel",
            "subscription",
            "task_id",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["unsubscribe", "list"],
                    "default": "unsubscribe",
                    "description": _(
                        "param.action.description",
                        default="Action: 'unsubscribe' (default) to cancel by task_id, or 'list' to show active subscriptions.",
                    ),
                },
                "task_id": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.task_id.description",
                        default="COV task_id to unsubscribe (required for action=unsubscribe).",
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


def _format_sub_list(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    subs = payload.get("subscriptions") or []
    if not subs:
        return _("msg.no_subscriptions", default="No active COV subscriptions.")
    lines = [
        _(
            "msg.subscriptions_header",
            default="Active COV subscriptions ({count}):",
            count=len(subs),
        )
    ]
    for s in subs:
        label = s.get("label") or f"{s.get('object_type')}:{s.get('object_instance')}"
        lines.append(
            f"  [{s.get('task_id')}] {label} @ {s.get('ip')} [{s.get('status')}]"
        )
    return "\n".join(lines).strip()


def _format_unsub(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.unsubscribed",
        default="COV subscription task_id={task_id} cancelled.",
        task_id=payload.get("task_id", "?"),
    )


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "unsubscribe").strip().lower()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if action == "list":
        result = cov_list()
        if output_format == "text":
            return _format_sub_list(result)
        return json.dumps(result, ensure_ascii=False)

    task_id = args.get("task_id")
    if task_id is None:
        err = _(
            "err.task_id_required",
            default="task_id is required for action=unsubscribe.",
        )
        payload = {"ok": False, "error": err}
        return (
            f"Error: {err}"
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    result = cov_unsubscribe(int(task_id))

    if output_format == "text":
        return _format_unsub(result)
    return json.dumps(result, ensure_ascii=False)
