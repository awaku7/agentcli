from __future__ import annotations

import json
from typing import Any

from .bacnet_shared import cov_subscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:bacnet_cov_subscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "bacnet_cov_subscribe",
        "description": _(
            "tool.description",
            default=(
                "Subscribe to BACnet COV (Change of Value) notifications for an object. "
                "When the value changes, the LLM is automatically notified. "
                "Returns a task_id for later unsubscription."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "bacnet cov subscribe",
                "bacnet_cov_subscribe",
                "bacnet",
                "BACNET",
                "cov",
                "change",
                "value",
                "notifications",
            ],
        ),
        "x_search_terms_en": [
            "bacnet cov subscribe",
            "bacnet_cov_subscribe",
            "bacnet",
            "BACNET",
            "cov",
            "change",
            "value",
            "notifications",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Target device IPv4 address.",
                    ),
                },
                "object_type": {
                    "type": "string",
                    "enum": [
                        "analogInput",
                        "analogOutput",
                        "analogValue",
                        "binaryInput",
                        "binaryOutput",
                        "binaryValue",
                        "multiStateInput",
                        "multiStateOutput",
                        "multiStateValue",
                    ],
                    "description": _(
                        "param.object_type.description",
                        default="BACnet object type to monitor.",
                    ),
                },
                "object_instance": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.object_instance.description",
                        default="BACnet object instance number.",
                    ),
                },
                "lifetime": {
                    "type": "integer",
                    "default": 900,
                    "minimum": 60,
                    "description": _(
                        "param.lifetime.description",
                        default="Subscription lifetime in seconds (default: 900). BAC0 auto-renews.",
                    ),
                },
                "confirmed": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.confirmed.description",
                        default="Use confirmed COV (acknowledged). Default: False (unconfirmed).",
                    ),
                },
                "label": {
                    "type": "string",
                    "description": _(
                        "param.label.description",
                        default="Human-readable label for this subscription (e.g. '3F会議室_室温').",
                    ),
                },
                "on_change_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_change_prompt.description",
                        default=(
                            "Optional prompt injected into the LLM when a change is detected. "
                            "If omitted, a default description is generated from the label and values."
                        ),
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
            "required": ["ip", "object_type", "object_instance"],
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
            "msg.subscribed",
            default="COV subscription active: task_id={task_id}, {label}",
        ).format(
            task_id=payload.get("task_id", "?"),
            label=sub.get("label")
            or f"{sub.get('object_type')}:{sub.get('object_instance')}",
        )
    ]
    lines.append(f"  ip: {sub.get('ip')}")
    lines.append(f"  object: {sub.get('object_type')}:{sub.get('object_instance')}")
    lines.append(f"  lifetime: {sub.get('lifetime')}s")
    if sub.get("label"):
        lines.append(f"  label: {sub.get('label')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip = str(args.get("ip") or "").strip()
    object_type = str(args.get("object_type") or "").strip()
    object_instance = int(args.get("object_instance", 0))
    lifetime = int(args.get("lifetime", 900))
    confirmed = bool(args.get("confirmed", False))
    label = str(args.get("label") or "").strip()
    on_change_prompt = str(args.get("on_change_prompt") or "").strip()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip:
        err = _("err.ip_required", default="ip is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)
    if not object_type:
        err = _("err.object_type_required", default="object_type is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    result = cov_subscribe(
        ip=ip,
        object_type=object_type,
        object_instance=object_instance,
        lifetime=lifetime,
        confirmed=confirmed,
        label=label,
        on_change_prompt=on_change_prompt,
    )

    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
