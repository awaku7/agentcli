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
        "name": "mcp_prompts",
        "description": _(
            "tool.description",
            default="List MCP prompts or get a prompt from an MCP server.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["mcp prompts", "mcp prompt", "get mcp prompt"],
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get"],
                    "description": _(
                        "param.action.description",
                        default="Use list to enumerate prompts or get to retrieve one.",
                    ),
                    "default": "list",
                },
                "name": {
                    "type": "string",
                    "description": _(
                        "param.name.description",
                        default="Prompt name required when action=get.",
                    ),
                },
                "arguments": {
                    "type": "object",
                    "additionalProperties": True,
                    "description": _(
                        "param.arguments.description",
                        default="Optional prompt arguments for action=get.",
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


async def _request(
    connection: dict[str, Any],
    action: str,
    name: str,
    arguments: dict[str, str] | None,
) -> Any:
    async with MCPClient(**connection) as client:
        if action == "get":
            return await client.get_prompt(name, arguments)
        return await client.list_prompts()


def run_tool(args: dict[str, Any]) -> str:
    args = args or {}
    action = str(args.get("action") or "list").strip().lower()
    if action not in {"list", "get"}:
        return _("err.action", default="Error: action must be list or get.")
    name = str(args.get("name") or "").strip()
    if action == "get" and not name:
        return _("err.name_required", default="Error: name is required for get.")
    arguments = args.get("arguments")
    if arguments is not None and not isinstance(arguments, dict):
        return _(
            "err.arguments_object",
            default="Error: arguments must be an object.",
        )
    try:
        connection, _resolved_name = _resolve(args)
        if not connection.get("url") and not connection.get("command"):
            return _(
                "err.endpoint_required", default="Error: MCP endpoint is required."
            )
        connection["protocol_mode"] = str(
            args.get("protocol_mode") or connection.get("protocol_mode") or "auto"
        )
        result = asyncio.run(_request(connection, action, name, arguments))
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        return _(
            "err.request", default="Error: MCP prompt request failed: %(error)s"
        ) % {"error": exc}
