from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator
from .opcua_shared import sync_run

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:opcua_browse"

_DEFAULT_TIMEOUT = 10

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "opcua_browse",
        "description": _(
            "tool.description",
            default=(
                "Browse the OPC UA server address space. "
                "Returns child nodes of the specified starting node."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "opcua browse",
                "opcua_browse",
                "opcua",
                "OPCUA",
                "server",
                "address",
                "space",
                "returns",
            ],
        ),
        "x_search_terms_en": [
            "opcua browse",
            "opcua_browse",
            "opcua",
            "OPCUA",
            "server",
            "address",
            "space",
            "returns",
        ],
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
                "node_id": {
                    "type": "string",
                    "description": _(
                        "param.node_id.description",
                        default=(
                            "Starting node ID (e.g. 'i=84' for Objects folder, "
                            "'ns=2;s=MyVariable'). Default: i=84 (Objects)."
                        ),
                    ),
                },
                "depth": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 5,
                    "description": _(
                        "param.depth.description",
                        default="Browse depth (1=children only, 2=grandchildren, etc.). Max 5.",
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
            "required": ["url"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_node_id(text: str, ua: Any) -> Any:
    """Parse a node ID string into a NodeId object."""
    text = text.strip()
    if text.startswith("i="):
        return ua.NodeId(int(text[2:]), 0)
    if text.startswith("ns="):
        parts = text.split(";")
        ns = 0
        identifier = text
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
        return ua.NodeId(identifier, ns)
    # Default: treat as string
    return ua.NodeId(text, 0)


async def _browse_recursive(
    client, ua, node_id, depth: int, max_depth: int
) -> list[dict[str, Any]]:
    """Browse children recursively up to max_depth."""
    items: list[dict[str, Any]] = []
    try:
        node = client.get_node(node_id)
        children = await node.get_children()
    except Exception:
        return items

    for child in children:
        try:
            attrs = await child.read_attributes(
                [
                    ua.AttributeIds.NodeId,
                    ua.AttributeIds.DisplayName,
                    ua.AttributeIds.BrowseName,
                    ua.AttributeIds.NodeClass,
                    ua.AttributeIds.Description,
                ]
            )
            node_id_str = (
                str(attrs[0].Value.Value) if attrs[0].Value else str(child.nodeid)
            )
            display_name = str(attrs[1].Value.Value.Text) if attrs[1].Value else ""
            browse_name = str(attrs[2].Value.Value.Name) if attrs[2].Value else ""
            node_class = str(attrs[3].Value.Value) if attrs[3].Value else "Unknown"
            desc = (
                str(attrs[4].Value.Value) if len(attrs) > 4 and attrs[4].Value else ""
            )

            item = {
                "node_id": node_id_str,
                "display_name": display_name,
                "browse_name": browse_name,
                "node_class": node_class,
                "description": desc[:200] if desc else None,
            }

            if depth < max_depth:
                item["children"] = await _browse_recursive(
                    client, ua, child.nodeid, depth + 1, max_depth
                )

            items.append(item)
        except Exception:
            pass

    return items


def _format_tree(items: list[dict[str, Any]], indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = "  " * indent
    for item in items:
        name = (
            item.get("display_name")
            or item.get("browse_name")
            or item.get("node_id", "?")
        )
        lines.append(f"{prefix}- {name} [{item.get('node_class')}]")
        lines.append(f"{prefix}  id: {item.get('node_id')}")
        if item.get("description"):
            lines.append(f"{prefix}  desc: {item.get('description')}")
        for child in item.get("children", []):
            lines.extend(_format_tree([child], indent + 1))
    return lines


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    lines = [
        _(
            "msg.summary",
            default="OPC UA browse: {count} node(s) from {node} in {ms} ms.",
            count=len(payload.get("nodes", [])),
            node=payload.get("target", {}).get("node_id", "?"),
            ms=payload.get("elapsed_ms", 0),
        )
    ]
    lines.extend(_format_tree(payload.get("nodes", [])))
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    url = str(args.get("url") or "").strip()
    node_id_text = str(args.get("node_id") or "i=84").strip()
    depth = min(int(args.get("depth", 1)), 5)
    timeout = int(args.get("timeout", _DEFAULT_TIMEOUT))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not url:
        err = _("err.url_required", default="url is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    start_time = time.monotonic()

    async def _browse(client, ua):
        node_id = _parse_node_id(node_id_text, ua)
        nodes = await _browse_recursive(client, ua, node_id, 1, depth)
        return nodes

    try:
        nodes = sync_run(_browse, url, timeout)

        payload = {
            "ok": True,
            "count": len(nodes),
            "nodes": nodes,
            "target": {
                "url": url,
                "node_id": node_id_text,
                "depth": depth,
            },
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }

        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)

    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": str(exc),
            "target": {"url": url, "node_id": node_id_text},
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
