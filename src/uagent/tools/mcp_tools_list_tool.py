from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import json
import asyncio
import os
from dataclasses import asdict, is_dataclass
from ..env_utils import env_get
from typing import Any

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.stdio import stdio_client, StdioServerParameters
except ImportError:
    from .._pip_auto import install_with_status as _install_mcp

    if not _install_mcp("mcp"):
        raise
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
            return os.path.join(
                os.path.expanduser("~"), ".uag", "mcps", "mcp_servers.json"
            )


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "tool_genre": "external",
    "function": {
        "name": "mcp_tools_list",
        "description": _(
            "tool.description",
            default="Connect to an MCP server and list available tools. Supports HTTP and stdio transports.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "mcps_list",
                "mcps list",
            ],
        ),
        "x_search_terms_en": [
            "mcps_list",
            "mcps list",
        ],
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


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]

    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value))
        except Exception:
            pass

    for method_name in ("model_dump", "dict", "to_dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return _to_jsonable(method())
            except Exception:
                pass

    if hasattr(value, "__dict__"):
        try:
            return _to_jsonable(vars(value))
        except Exception:
            pass

    return str(value)


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
                        "inputSchema": _to_jsonable(
                            t.inputSchema
                            if hasattr(t, "inputSchema")
                            else getattr(t, "input_schema", {})
                        ),
                    }
                )

        return {
            "initialize": _to_jsonable(init_result),
            "tools_list": {"tools": tools},
        }


def _resolve_http_headers(raw: Any) -> dict[str, str]:
    """Build HTTP headers for MCP streamable HTTP.

    Supports plain strings and env refs: "env:VAR" or "${VAR}".
    """

    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if not key:
            continue
        val = "" if v is None else str(v)
        s = val.strip()
        if s.startswith("env:"):
            env_name = s[4:].strip()
            val = env_get(env_name, "") or os.environ.get(env_name, "")
        elif s.startswith("${") and s.endswith("}") and len(s) > 3:
            env_name = s[2:-1].strip()
            val = env_get(env_name, "") or os.environ.get(env_name, "")
        out[key] = str(val)
    return out


async def _mcp_tools_list_http(
    url: str, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    mcp_url = url if url.endswith("/mcp") else url.rstrip("/") + "/mcp"
    http_client = None
    if headers:
        try:
            import httpx
        except ImportError:
            from .._pip_auto import install_with_status as _install_httpx

            if not _install_httpx("httpx"):
                raise
            import httpx

        http_client = httpx.AsyncClient(headers=headers)
    try:
        async with streamable_http_client(
            mcp_url, http_client=http_client
        ) as (read, write, session_id):
            result = await _get_tools_from_session(read, write)
            result["url"] = mcp_url
            return result
    finally:
        if http_client is not None:
            await http_client.aclose()


async def _mcp_tools_list_stdio(
    command: str, args: list[str], env: dict[str, str]
) -> dict[str, Any]:
    server_params = StdioServerParameters(
        command=command, args=args, env={**os.environ, **(env or {})}
    )
    async with stdio_client(server_params) as (read, write):
        result = await _get_tools_from_session(read, write)
        result["command"] = command
        result["args"] = args
        return result


def run_tool(args: dict[str, Any]) -> str:
    args = args or {}

    url = args.get("url")
    server_name = args.get("server_name")
    pretty = bool(args.get("pretty", True))
    # Resolve url/command from config if needed
    command = ""
    cmd_args: list[str] = []
    cmd_env: dict[str, str] = {}
    http_headers: dict[str, str] = {}

    if (not url) and server_name:
        try:
            config_path = str(get_default_mcp_config_path())
            if config_path and os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                servers = cfg.get("mcp_servers") if isinstance(cfg, dict) else []
                if isinstance(servers, list):
                    for s in servers:
                        if isinstance(s, dict) and s.get("name") == server_name:
                            url = s.get("url")
                            command = str(s.get("command") or "")
                            raw_args = s.get("args") or []
                            cmd_args = (
                                [str(x) for x in raw_args]
                                if isinstance(raw_args, list)
                                else []
                            )
                            raw_env = s.get("env") or {}
                            cmd_env = (
                                {str(k): str(v) for k, v in raw_env.items()}
                                if isinstance(raw_env, dict)
                                else {}
                            )
                            http_headers = _resolve_http_headers(s.get("headers"))
                            break
        except Exception:
            pass

    if not url and not server_name:
        return json.dumps(
            {"ok": False, "error": "Either 'url' or 'server_name' must be provided."},
            ensure_ascii=False,
        )

    # If neither url nor command is resolved, fail early.
    if (not url) and (not command):
        return json.dumps(
            {
                "ok": False,
                "error": "MCP server is not configured (no url/command).",
                "server_name": server_name,
            },
            ensure_ascii=False,
        )

    try:
        # 1) stdio via configured command
        if (not url) and command:
            result = asyncio.run(_mcp_tools_list_stdio(command, cmd_args, cmd_env))

        # 2) stdio shorthand url
        elif isinstance(url, str) and url.startswith("stdio://"):
            cmd = url[len("stdio://") :]
            # no args/env in shorthand
            result = asyncio.run(_mcp_tools_list_stdio(cmd, [], {}))

        # 3) http
        else:
            result = asyncio.run(_mcp_tools_list_http(str(url), http_headers))

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
