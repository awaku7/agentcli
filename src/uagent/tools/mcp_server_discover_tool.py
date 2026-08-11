from __future__ import annotations

import asyncio
import json
from typing import Any

from .i18n_helper import make_tool_translator
from .mcp.client import MCPClient
from .mcp_resources_tool import _resolve

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "tool_genre": "external",
    "function": {
        "name": "mcp_server_discover",
        "description": _(
            "tool.description",
            default="Discover an MCP server's protocol versions, capabilities, and identity.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["mcp discover", "mcp server discovery", "mcp capabilities"],
        ),
        "parameters": {
            "type": "object",
            "properties": {
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
                    "default": "stateless",
                },
            },
            "required": [],
        },
    },
}


async def _request(connection: dict[str, Any]) -> Any:
    async with MCPClient(**connection) as client:
        return await client.discover()


def run_tool(args: dict[str, Any]) -> str:
    args = args or {}
    try:
        connection, _resolved_name = _resolve(args)
        if not connection.get("url") and not connection.get("command"):
            return _(
                "err.endpoint_required", default="Error: MCP endpoint is required."
            )
        connection["protocol_mode"] = str(
            args.get("protocol_mode") or connection.get("protocol_mode") or "stateless"
        )
        result = asyncio.run(_request(connection))
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        return _("err.request", default="Error: MCP discovery failed: %(error)s") % {
            "error": exc
        }
