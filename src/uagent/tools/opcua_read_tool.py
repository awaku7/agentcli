from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator
from .opcua_shared import sync_run

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:opcua_read"

_DEFAULT_TIMEOUT = 10

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "opcua_read",
        "description": _(
            "tool.description",
            default=(
                "Read node value(s) from an OPC UA server. "
                "Returns the current value and metadata."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="OPC UA server URL (e.g. 'opc.tcp://192.168.1.101:4840').",
                    ),
                },
                "node_ids": {
                    "type": "string",
                    "description": _(
                        "param.node_ids.description",
                        default=(
                            "Node ID(s) to read. Single: 'i=85' or 'ns=2;s=Temp'. "
                            "Multiple: comma-separated 'i=85,ns=2;s=Pressure'."
                        ),
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
            "required": ["url", "node_ids"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_node_ids(text: str, ua: Any) -> list[Any]:
    """Parse comma-separated node IDs."""
    result: list[Any] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("i="):
            result.append(ua.NodeId(int(part[2:]), 0))
        elif part.startswith("ns="):
            parts = part.split(";")
            ns = 0
            identifier = part
            for p in parts:
                p = p.strip()
                if p.startswith("ns="):
                    ns = int(p[3:])
                elif p.startswith("s="):
                    identifier = p[2:]
                elif p.startswith("i="):
                    identifier = int(p[2:])
                elif p.startswith("b="):
                    identifier = bytes.fromhex(p[2:])
            result.append(ua.NodeId(identifier, ns))
        else:
            result.append(ua.NodeId(part, 0))
    return result


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    results = payload.get("results", [])
    lines = [
        _("msg.summary",
          default="OPC UA read: {count} value(s) in {ms} ms.",
          count=len(results),
          ms=payload.get("elapsed_ms", 0))
    ]
    for r in results:
        lines.append(f"  {r.get('node_id')} = {r.get('value')} [{r.get('type')}]")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    url = str(args.get("url") or "").strip()
    node_ids_text = str(args.get("node_ids") or "").strip()
    timeout = int(args.get("timeout", _DEFAULT_TIMEOUT))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not url:
        return json.dumps({"ok": False, "error": "url is required."}, ensure_ascii=False)
    if not node_ids_text:
        return json.dumps({"ok": False, "error": "node_ids is required."}, ensure_ascii=False)

    start_time = time.monotonic()

    async def _read(client, ua):
        nodes = _parse_node_ids(node_ids_text, ua)
        results = []
        for nid in nodes:
            try:
                node = client.get_node(nid)
                val = await node.read_value()
                data_val = await node.read_data_value()
                results.append({
                    "node_id": str(nid),
                    "value": str(val) if val is not None else None,
                    "type": type(val).__name__ if val is not None else "None",
                    "source_timestamp": str(getattr(data_val, 'SourceTimestamp', '')),
                    "status": str(getattr(data_val, 'StatusCode', '')),
                })
            except Exception as e:
                results.append({
                    "node_id": str(nid),
                    "error": str(e),
                })
        return results

    try:
        results = sync_run(_read, url, timeout)
        payload = {
            "ok": True,
            "count": len(results),
            "results": results,
            "target": {"url": url, "node_ids": node_ids_text},
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        err = {"ok": False, "error": str(exc), "elapsed_ms": int((time.monotonic() - start_time) * 1000)}
        return json.dumps(err, ensure_ascii=False) if output_format != "text" else f"Error: {exc}"
