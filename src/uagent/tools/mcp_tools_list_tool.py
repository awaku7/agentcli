from __future__ import annotations

import json
import asyncio
import os
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.client.stdio import stdio_client, StdioServerParameters

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        import os

        return os.path.join(
            os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json"
        )


from .context import get_callbacks

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_tools_list",
        "description": (
            "【最優先】MCP(Model Context Protocol)サーバーへ接続し、提供されている tools 一覧を取得して返します。\n"
            "何らかの操作（API連携、システム操作等）を行う際は、まずこのツールで利用可能なMCPツールを確認してください。\n"
            "想定: HTTP ベース または stdio ベースの MCP サーバー。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "MCPサーバーのエンドポイントURL。設定ファイルまたはcommandを使う場合は省略可。"
                    ),
                },
                "server_name": {
                    "type": "string",
                    "description": "設定ファイル内のサーバー名（name）で指定する場合に使用します。",
                },
                "pretty": {
                    "type": "boolean",
                    "description": "true の場合は JSON を見やすく整形して返す（既定: true）",
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
        return result


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    url = str(args.get("url", "")).strip()
    server_name = str(args.get("server_name", "")).strip()

    command = ""
    cmd_args = []
    cmd_env = {}

    # 設定ファイルからの解決
    config_path = get_default_mcp_config_path()

    if server_name:
        # 名前指定がある場合、設定ファイルから該当を探す
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    servers = config.get("mcp_servers", [])
                    found = False
                    for s in servers:
                        if s.get("name") == server_name:
                            url = s.get("url", "")
                            command = s.get("command", "")
                            cmd_args = s.get("args", [])
                            cmd_env = s.get("env", {})
                            found = True
                            break
                    if not found and not url:
                        return f"Error: Server with name '{server_name}' not found in {config_path}"
            except Exception as e:
                return f"Error loading MCP config ({config_path}): {e}"
    elif not url:
        # 名前指定もURL指定もない場合、デフォルト(0番目)を使う
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    servers = config.get("mcp_servers", [])
                    if servers:
                        s = servers[0]
                        url = s.get("url", "")
                        command = s.get("command", "")
                        cmd_args = s.get("args", [])
                        cmd_env = s.get("env", {})
            except Exception as e:
                return f"Error loading MCP config ({config_path}): {e}"

    # デフォルトフォールバック (http)
    if not url and not command:
        # handle_mcp_v2 のデフォルトに合わせるが、stdioかhttpか不明
        return (
            "MCP server is not configured. Please add a server via mcp_servers_add (or create a config via mcp_servers_init_template) "
            "and then specify server_name/url. (No operation performed)"
        )

    pretty = bool(args.get("pretty", True))

    try:
        if command:
            # stdio mode
            results = asyncio.run(_mcp_tools_list_stdio(command, cmd_args, cmd_env))
            source_info = f"command: {command} {' '.join(cmd_args)}"
        else:
            # http mode
            results = asyncio.run(_mcp_tools_list_http(url))
            source_info = f"url: {results.get('url', url)}"

        init_result = results.get("initialize")
        tools_list = results.get("tools_list", {})
        tools = tools_list.get("tools", [])

        lines: List[str] = []
        lines.append(f"MCP tools/list from: {source_info}")
        if server_name:
            lines.append(f"Server Name: {server_name}")

        if init_result:
            # init_result は通常 InitializeResult オブジェクトだが、SDK差分に耐えるため安全に抽出する
            def _extract_server_info(initialize_result: Any) -> Dict[str, Any]:
                if initialize_result is None:
                    return {}
                if isinstance(initialize_result, dict):
                    si = initialize_result.get("serverInfo")
                    return si if isinstance(si, dict) else {}
                if hasattr(initialize_result, "serverInfo"):
                    si = getattr(initialize_result, "serverInfo")
                    if isinstance(si, dict):
                        return si
                    if si is None:
                        return {}
                    out: Dict[str, Any] = {}
                    name = getattr(si, "name", None)
                    version = getattr(si, "version", None)
                    if name is not None:
                        out["name"] = name
                    if version is not None:
                        out["version"] = version
                    return out
                return {}

            si = _extract_server_info(init_result)
            si_name = si.get("name", "Unknown")
            si_ver = si.get("version", "Unknown")
            lines.append(f"serverInfo: name={si_name!r} version={si_ver!r}")

        lines.append(f"tools: {len(tools)}")
        for t in tools:
            t_name = t.get("name")
            t_desc = t.get("description")
            lines.append(f"- {t_name}: {t_desc}")

        lines.append("")
        lines.append("raw JSON:")

        # オブジェクトのシリアライズ対応
        def default_encoder(o):
            if hasattr(o, "dict"):
                return o.dict()
            if hasattr(o, "__dict__"):
                return o.__dict__
            return str(o)

        if pretty:
            lines.append(
                json.dumps(
                    results,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=default_encoder,
                )
            )
        else:
            lines.append(
                json.dumps(results, ensure_ascii=False, default=default_encoder)
            )

        return cb.truncate_output("mcp_tools_list", "\n".join(lines), limit=200_000)

    except Exception as e:
        return f"Error in mcp_tools_list: {type(e).__name__}: {e}"
