from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import asyncio
import os
from ..env_utils import env_get
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.client.stdio import stdio_client, StdioServerParameters

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        import os

        env_path = env_get("UAGENT_MCP_CONFIG")
        if env_path:
            return os.path.abspath(os.path.expanduser(env_path))

        try:
            from uagent.utils.paths import get_mcp_servers_json_path

            return str(get_mcp_servers_json_path())
        except Exception:
            p_new = os.path.join(
                os.path.expanduser("~"), ".uag", "mcps", "mcp_servers.json"
            )
            if os.path.exists(p_new):
                return p_new
            return os.path.join(
                os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json"
            )


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_tools_list",
        "description": _(
            "tool.description",
            default=(
                "[Highest priority] Connect to an MCP (Model Context Protocol) server and return the list of available tools. "
                "Before performing any API/system integration, use this tool to discover what MCP tools are available. "
                "Supports HTTP-based and stdio-based MCP servers."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Connect to an MCP server (HTTP or stdio) and list its tools. "
                "Prefer using configured servers in mcp_servers.json when possible."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default=(
                            "MCP server endpoint URL. If omitted, a configured server may be used."
                        ),
                    ),
                },
                "server_name": {
                    "type": "string",
                    "description": _(
                        "param.server_name.description",
                        default="Server name from the config file (mcp_servers[].name).",
                    ),
                },
                "pretty": {
                    "type": "boolean",
                    "description": _(
                        "param.pretty.description",
                        default="If true, pretty-print JSON output (default: true).",
                    ),
                    "default": True,
                },
            },
            "required": [],
        },
    },
}


async def _get_tools_from_session(read, write):
    async with ClientSession(read, write) as session:
        init_result = await session.initialize()
        tools_result = await session.list_tools()

        tools = []
        if hasattr(tools_result, "tools"):
            for t in tools_result.tools:
                tools.append(
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": (
                            t.inputSchema
                            if hasattr(t, "inputSchema")
                            else getattr(t, "input_schema", {})
                        ),
                    }
                )

        return {
            "initialize": init_result,
            "tools_list": {"tools": tools},
        }


async def _mcp_tools_list_http(url: str) -> Dict[str, Any]:
    mcp_url = url if url.endswith("/mcp") else url.rstrip("/") + "/mcp"
    async with streamable_http_client(mcp_url) as (read, write, session_id):
        result = await _get_tools_from_session(read, write)
        result["url"] = mcp_url
        return result


async def _mcp_tools_list_stdio(
    command: str, args: List[str], env: Dict[str, str]
) -> Dict[str, Any]:
    server_params = StdioServerParameters(
        command=command, args=args, env={**os.environ, **(env or {})}
    )
    async with stdio_client(server_params) as (read, write):
        result = await _get_tools_from_session(read, write)
        result["command"] = command
        result["args"] = args
        return result


def run_tool(args: Dict[str, Any]) -> str:
    args = args or {}

    url = args.get("url")
    server_name = args.get("server_name")
    pretty = bool(args.get("pretty", True))

    # Resolve url from config if needed
    if (not url) and server_name:
        try:
            from .mcp_servers_list_tool import run_tool as list_servers

            raw = list_servers(
                {
                    "path": None,
                    "pretty": False,
                    "validate": False,
                    "default_only": False,
                    "raw": True,
                }
            )
            # list_servers returns json text or text; try parse
            obj = json.loads(raw) if raw.strip().startswith("{") else None
            if obj and isinstance(obj, dict):
                servers = obj.get("mcp_servers") or []
                for s in servers:
                    if isinstance(s, dict) and s.get("name") == server_name:
                        url = s.get("url")
                        break
        except Exception:
            pass

    if not url and not server_name:
        return json.dumps(
            {"ok": False, "error": "Either 'url' or 'server_name' must be provided."},
            ensure_ascii=False,
        )

    try:
        # If url looks like stdio://command, treat it as stdio shorthand.
        if isinstance(url, str) and url.startswith("stdio://"):
            cmd = url[len("stdio://") :]
            # no args/env in shorthand
            result = asyncio.run(_mcp_tools_list_stdio(cmd, [], {}))
        else:
            result = asyncio.run(_mcp_tools_list_http(str(url)))

        if pretty:
            return json.dumps(result, ensure_ascii=False, indent=2)
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": str(e),
            },
            ensure_ascii=False,
        )
