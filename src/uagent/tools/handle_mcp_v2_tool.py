from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import json
import asyncio
import sys
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


from .context import get_callbacks


def mask_values(data: Any) -> Any:
    """Replace values in a dictionary or list with '*' (preserving structure)."""
    if isinstance(data, dict):
        return {k: mask_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [mask_values(v) for v in data]
    else:
        return "*"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "handle_mcp_v2",
        "description": _(
            "tool.description",
            default="Call a tool from an MCP server. Provide tool arguments as a dictionary in tool_arguments.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": _(
                        "param.server_name.description",
                        default="Server name defined in mcp_servers.json. If specified, it takes priority over url.",
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="MCP server endpoint URL (http://... or stdio://command...).",
                    ),
                },
                "tool_name": {
                    "type": "string",
                    "description": _(
                        "param.tool_name.description",
                        default="The name of the tool to execute.",
                    ),
                },
                "tool_arguments": {
                    "type": "object",
                    "description": _(
                        "param.tool_arguments.description",
                        default='A dictionary of arguments to pass to the tool. Example: {"handle": "you.bsky.social", "password": "xxxx"}',
                    ),
                },
            },
            "required": ["tool_name"],
        },
    },
}


async def _call_mcp_stdio(
    command: str, args: List[str], env: Dict[str, str], name: str, argv: Dict[str, Any]
) -> str:
    server_params = StdioServerParameters(
        command=command, args=args, env={**os.environ, **(env or {})}
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, argv)
                return _format_result(result)
    except Exception as e:
        return f"[Error] MCP stdio call failed: {str(e)}"


async def _call_mcp_http(url: str, name: str, argv: Dict[str, Any]) -> str:
    mcp_url = url if url.endswith("/mcp") else url.rstrip("/") + "/mcp"
    try:
        async with streamable_http_client(mcp_url) as (read, write, session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, argv)
                return _format_result(result)
    except Exception as e:
        return f"[Error] MCP http call failed: {str(e)}"


def _format_result(result: Any) -> str:
    """Format MCP tool results for LLM.

    If the tool returns a file payload, save it under ./downloads and only return the saved path.

    Supported payload shapes:
    - Plain dict: {"filename": str, "mime": str, "data_base64": str}
    - Content blocks (best-effort): objects that expose attributes like filename/name + data_base64/blob
    """

    def _save_download(filename: str, data: bytes) -> str:
        dl_dir = os.path.abspath(os.path.join(os.getcwd(), "downloads"))
        os.makedirs(dl_dir, exist_ok=True)

        base = os.path.basename(filename) or "download.bin"
        save_path = os.path.join(dl_dir, base)

        # Avoid overwrite collisions
        if os.path.exists(save_path):
            root, ext = os.path.splitext(base)
            for i in range(1, 1000):
                cand = os.path.join(dl_dir, f"{root}_{i}{ext}")
                if not os.path.exists(cand):
                    save_path = cand
                    break

        with open(save_path, "wb") as f:
            f.write(data)
        return save_path

    # 0) If server returned plain dict payload
    try:
        if isinstance(result, dict) and result.get("data_base64") and result.get("filename"):
            import base64

            raw = base64.b64decode(result.get("data_base64") or "")
            path = _save_download(str(result.get("filename")), raw)
            return f"[Saved] {path}"
    except Exception as e:
        return f"[Error] Failed to save returned file payload: {e}"

    output_parts: List[str] = []

    # 1) ToolResult-like with content blocks
    if hasattr(result, "content"):
        for content in result.content:
            # TextContent
            if hasattr(content, "text"):
                output_parts.append(content.text)
                continue

            # ImageContent (keep existing behavior)
            if hasattr(content, "data") and hasattr(content, "mimeType"):
                output_parts.append(f"[Binary/Image data: {content.mimeType}]")
                continue

            # Best-effort: resource/binary block with base64
            try:
                import base64

                # Try common attribute names
                b64 = getattr(content, "blob", None) or getattr(content, "data_base64", None)
                fname = getattr(content, "filename", None) or getattr(content, "name", None)

                # Some SDKs wrap resource under .resource
                res = getattr(content, "resource", None)
                if res is not None:
                    b64 = b64 or getattr(res, "blob", None) or getattr(res, "data_base64", None)
                    fname = fname or getattr(res, "filename", None) or getattr(res, "name", None)

                if b64:
                    raw = base64.b64decode(b64)
                    path = _save_download(str(fname or "download.bin"), raw)
                    output_parts.append(f"[Saved] {path}")
                    continue

            except Exception as e:
                output_parts.append(f"[Warn] Unhandled binary-like content: {e}")
                continue

    if not output_parts:
        return json.dumps(
            result,
            default=lambda x: str(x),
            ensure_ascii=False,
            indent=2,
        )
    return "\n".join(output_parts)



def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    server_name = str(args.get("server_name", "")).strip()
    url = args.get("url", "")
    name = args.get("tool_name")
    argv = args.get("tool_arguments", {})

    if not name:
        return _("err.tool_name_required", default="Error: tool_name is required.")

    masked_argv = mask_values(argv)
    print(f"\n[MCP Call] Tool: {name}", file=sys.stderr)
    print(f"[MCP Args] {json.dumps(masked_argv, ensure_ascii=False)}", file=sys.stderr)

    command = ""
    cmd_args = []
    cmd_env = {}

    config_path = get_default_mcp_config_path()
    if server_name:
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
                return f"Error loading MCP config: {e}"

    if not url and not command:
        if server_name:
            pass
        else:
            return (
                "MCP server is not configured. Please add a server via mcp_servers_add (or create a config via mcp_servers_init_template) "
                "and then specify server_name/url. (No operation performed)"
            )

    try:
        if command:
            result_text = asyncio.run(
                _call_mcp_stdio(command, cmd_args, cmd_env, name, argv)
            )
        elif url.startswith("stdio://"):
            parts = url[8:].strip().split()
            if not parts:
                return _("err.stdio_url_invalid", default="Error: Invalid stdio url")
            result_text = asyncio.run(
                _call_mcp_stdio(parts[0], parts[1:], {}, name, argv)
            )
        else:
            result_text = asyncio.run(_call_mcp_http(url, name, argv))

        return cb.truncate_output("handle_mcp_v2", result_text, limit=200_000)

    except Exception as e:
        return f"Unexpected error in run_tool: {str(e)}"
