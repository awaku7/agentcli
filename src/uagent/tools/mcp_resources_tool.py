from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from ..env_utils import env_get
from .i18n_helper import make_tool_translator
from .mcp.client import MCPClient
from .mcp_servers_shared import get_default_mcp_config_path

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "tool_genre": "external",
    "function": {
        "name": "mcp_resources",
        "description": _(
            "tool.description",
            default="List MCP resources or read one resource from an MCP server.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["mcp resources", "mcp resource", "read mcp resource"],
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "read"],
                    "description": _(
                        "param.action.description",
                        default="Use list to enumerate resources or read to fetch a URI.",
                    ),
                    "default": "list",
                },
                "uri": {
                    "type": "string",
                    "description": _(
                        "param.uri.description",
                        default="Resource URI required when action=read.",
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="MCP endpoint URL, unless server_name is configured.",
                    ),
                },
                "server_name": {
                    "type": "string",
                    "description": _(
                        "param.server_name.description",
                        default="Configured MCP server name.",
                    ),
                },
                "protocol_mode": {
                    "type": "string",
                    "enum": ["auto", "legacy", "stateless"],
                    "description": _(
                        "param.protocol_mode.description",
                        default="MCP protocol mode: auto, legacy, or stateless.",
                    ),
                    "default": "auto",
                },
            },
            "required": [],
        },
    },
}


def _headers(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in raw.items():
        text = "" if value is None else str(value).strip()
        if text.startswith("env:"):
            text = env_get(text[4:].strip(), "") or os.environ.get(text[4:].strip(), "")
        elif text.startswith("${") and text.endswith("}"):
            name = text[2:-1].strip()
            text = env_get(name, "") or os.environ.get(name, "")
        result[str(key)] = text
    return result


def _resolve(args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    server_name = str(args.get("server_name") or "").strip()
    if not server_name:
        return {"url": str(args.get("url") or "")}, ""
    path = get_default_mcp_config_path()
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    for server in config.get("mcp_servers", []):
        if isinstance(server, dict) and server.get("name") == server_name:
            mode = str(args.get("protocol_mode") or server.get("protocol_mode") or "auto")
            return {
                "url": server.get("url") or None,
                "command": server.get("command") or None,
                "args": [str(item) for item in server.get("args", [])],
                "env": {str(k): str(v) for k, v in (server.get("env") or {}).items()},
                "headers": _headers(server.get("headers")),
                "protocol_mode": mode,
            }, server_name
    raise ValueError(f"MCP server not found: {server_name}")


async def _request(connection: dict[str, Any], action: str, uri: str) -> Any:
    async with MCPClient(**connection) as client:
        if action == "read":
            return await client.read_resource(uri)
        return await client.list_resources()


def run_tool(args: dict[str, Any]) -> str:
    args = args or {}
    action = str(args.get("action") or "list").strip().lower()
    if action not in {"list", "read"}:
        return _("err.action", default="Error: action must be list or read.")
    uri = str(args.get("uri") or "").strip()
    if action == "read" and not uri:
        return _("err.uri_required", default="Error: uri is required for read.")
    try:
        connection, _resolved_name = _resolve(args)
        if not connection.get("url") and not connection.get("command"):
            return _("err.endpoint_required", default="Error: MCP endpoint is required.")
        mode = str(args.get("protocol_mode") or connection.get("protocol_mode") or "auto")
        connection["protocol_mode"] = mode
        result = asyncio.run(_request(connection, action, uri))
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        return _("err.request", default="Error: MCP resource request failed: %(error)s") % {"error": exc}
