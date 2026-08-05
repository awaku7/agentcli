from __future__ import annotations

import json
from typing import Any

from .switchbot_shared import subscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:switchbot_subscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "switchbot_subscribe",
        "description": _(
            "tool.description",
            default=(
                "Subscribe to SwitchBot device status changes via polling. "
                "Since SwitchBot Cloud has no webhook, the device is polled "
                "at the specified interval. When a change is detected, "
                "the LLM is automatically notified."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "switchbot subscribe",
                "switchbot_subscribe",
                "switchbot",
                "changes",
                "polling",
            ],
        ),
        "x_search_terms_en": [
            "switchbot subscribe",
            "switchbot_subscribe",
            "switchbot",
            "changes",
            "polling",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "dev": {
                    "type": "string",
                    "description": _(
                        "param.dev.description",
                        default="SwitchBot device ID (required). Use switchbot_cloud_list to find it.",
                    ),
                },
                "interval": {
                    "type": "integer",
                    "default": 60,
                    "minimum": 10,
                    "description": _(
                        "param.interval.description",
                        default="Polling interval in seconds (minimum 10).",
                    ),
                },
                "label": {
                    "type": "string",
                    "description": _(
                        "param.label.description",
                        default="Human-readable label (e.g. 'Living_room_air_conditioner').",
                    ),
                },
                "on_change_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_change_prompt.description",
                        default="Optional prompt for LLM when state changes.",
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
            "required": ["dev"],
            "additionalProperties": False,
        },
    },
}


def _format_text(payload: dict[str, Any]) -> str:
    sub = payload.get("subscription") or {}
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    lines = [
        _(
            "msg.subscribed", default="SwitchBot subscription active: id={id}, {label}"
        ).format(
            id=payload.get("subscription_id", "?"),
            label=sub.get("label") or sub.get("device_id", ""),
        )
    ]
    lines.append(f"  device_id: {sub.get('device_id')}")
    lines.append(f"  interval: {sub.get('interval')}s")
    if sub.get("label"):
        lines.append(f"  label: {sub.get('label')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    device_id = str(args.get("dev") or "").strip()
    interval = int(args.get("interval", 60))
    label = str(args.get("label") or "").strip()
    on_change_prompt = str(args.get("on_change_prompt") or "").strip()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not device_id:
        err = _("err.dev_required", default="device_id (dev) is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    result = subscribe(
        device_id=device_id,
        interval=max(10, interval),
        label=label,
        on_change_prompt=on_change_prompt,
    )

    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
