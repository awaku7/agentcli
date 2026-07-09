from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator
from .opcua_shared import sync_run

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:opcua_write"

_DEFAULT_TIMEOUT = 10

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "opcua_write",
        "description": _(
            "tool.description",
            default=("Write a value to an OPC UA server node."),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["opcua write", "opcua_write", "opcua", "OPCUA", "value", "server"],
        ),
        "x_search_terms_en": [
            "opcua write",
            "opcua_write",
            "opcua",
            "OPCUA",
            "value",
            "server",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="OPC UA server URL.",
                    ),
                },
                "node_id": {
                    "type": "string",
                    "description": _(
                        "param.node_id.description",
                        default="Target node ID (e.g. 'i=85' or 'ns=2;s=Setpoint').",
                    ),
                },
                "value": {
                    "type": "string",
                    "description": _(
                        "param.value.description",
                        default="Value to write. Use type hint for non-string types.",
                    ),
                },
                "type": {
                    "type": "string",
                    "enum": ["string", "int", "float", "bool"],
                    "default": "string",
                    "description": _(
                        "param.type.description",
                        default="Data type hint for the value.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Connection timeout.",
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
            "required": ["url", "node_id", "value"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _convert_value(value_str: str, type_hint: str) -> Any:
    if type_hint == "int":
        return int(value_str)
    if type_hint == "float":
        return float(value_str)
    if type_hint == "bool":
        return value_str.strip().lower() in ("1", "true", "on", "yes")
    return value_str


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.summary",
        default="OPC UA write: {node} = {val}",
        node=payload.get("target", {}).get("node_id", "?"),
        val=payload.get("value_written", ""),
    )


def run_tool(args: dict[str, Any]) -> str:
    url = str(args.get("url") or "").strip()
    node_id_text = str(args.get("node_id") or "").strip()
    value_str = str(args.get("value") or "").strip()
    type_hint = str(args.get("type") or "string").strip().lower()
    timeout = int(args.get("timeout", _DEFAULT_TIMEOUT))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not url or not node_id_text or not value_str:
        return json.dumps(
            {"ok": False, "error": "url, node_id, value are required."},
            ensure_ascii=False,
        )

    start_time = time.monotonic()

    async def _write(client, ua):
        nid = None
        if node_id_text.startswith("i="):
            nid = ua.NodeId(int(node_id_text[2:]), 0)
        elif node_id_text.startswith("ns="):
            parts = node_id_text.split(";")
            ns = 0
            identifier = node_id_text
            for p in parts:
                p = p.strip()
                if p.startswith("ns="):
                    ns = int(p[3:])
                elif p.startswith("s="):
                    identifier = p[2:]
                elif p.startswith("i="):
                    identifier = int(p[2:])
            nid = ua.NodeId(identifier, ns)
        else:
            nid = ua.NodeId(node_id_text, 0)

        converted = _convert_value(value_str, type_hint)
        node = client.get_node(nid)
        await node.write_value(converted)
        return str(converted)

    try:
        written = sync_run(_write, url, timeout)
        payload = {
            "ok": True,
            "value_written": written,
            "target": {"url": url, "node_id": node_id_text, "type_hint": type_hint},
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": str(exc),
                "elapsed_ms": int((time.monotonic() - start_time) * 1000),
            },
            ensure_ascii=False,
        )
