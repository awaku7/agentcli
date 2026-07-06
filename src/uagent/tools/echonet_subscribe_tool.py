from __future__ import annotations

import json
from typing import Any

from .echonet_shared import subscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_subscribe"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "echonet_subscribe",
        "description": _(
            "tool.description",
            default=(
                "Subscribe to ECHONET Lite INF (notification) messages from a device. "
                "When the device sends an unsolicited property change notification, "
                "the LLM is automatically informed."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Target device IPv4 address to monitor (required).",
                    ),
                },
                "eoj": {
                    "type": "string",
                    "description": _(
                        "param.eoj.description",
                        default=(
                            "Optional EOJ filter (e.g. '013001' for a specific AC, "
                            "'0130' for all ACs). Omit to receive all notifications from this IP."
                        ),
                    ),
                },
                "label": {
                    "type": "string",
                    "description": _(
                        "param.label.description",
                        default="Human-readable label (e.g. 'リビング_エアコン').",
                    ),
                },
                "on_change_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_change_prompt.description",
                        default="Optional prompt injected into the LLM when a notification arrives.",
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
            "required": ["ip"],
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
            default="ECHONET Lite subscription active: id={id}, {label}",
        ).format(
            id=payload.get("listener_id", "?"),
            label=sub.get("label") or f"{sub.get('ip')}",
        )
    ]
    lines.append(f"  ip: {sub.get('ip')}")
    if sub.get("eoj"):
        lines.append(f"  eoj: {sub.get('eoj')}")
    lines.append(f"  label: {sub.get('label')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip = str(args.get("ip") or "").strip()
    eoj = str(args.get("eoj") or "").strip()
    label = str(args.get("label") or "").strip()
    on_change_prompt = str(args.get("on_change_prompt") or "").strip()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip:
        err = _("err.ip_required", default="ip is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    result = subscribe(ip=ip, eoj=eoj, label=label, on_change_prompt=on_change_prompt)

    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
