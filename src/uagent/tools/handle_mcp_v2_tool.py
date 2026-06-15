from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import json
import asyncio
import sys
import os
from ..env_utils import env_get
from typing import Any

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


from .context import get_callbacks


def _json_out(**payload: Any) -> str:
    """Return a stable JSON string for tool outputs.

    - Ensure_ascii=False for Japanese.
    - Drop None values to keep output compact.
    - default=str to avoid serialization errors.
    """

    data = {k: v for k, v in payload.items() if v is not None}
    return json.dumps(data, ensure_ascii=False, default=lambda x: str(x))


def mask_values(data: Any) -> Any:
    """Replace values in a dictionary or list with '*' (preserving structure)."""
    if isinstance(data, dict):
        return {k: mask_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [mask_values(v) for v in data]
    else:
        return "*"


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "handle_mcp_v2",
        "description": _(
            "tool.description",
            default="Call a tool from an MCP server. Provide tool arguments as a dictionary in tool_arguments.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "handle_mcp_v2",
                "handle mcp v2",
                "mcp tool",
                "model context protocol",
                "call remote tool",
                "mcp",
            ],
        ),
        "x_search_terms_en": [
            "handle_mcp_v2",
            "handle mcp v2",
            "mcp tool",
            "model context protocol",
            "call remote tool",
            "mcp",
        ],
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
                "args": {
                    "anyOf": [
                        {"type": "object", "additionalProperties": True},
                        {"type": "string"},
                    ],
                    "description": _(
                        "param.args.description",
                        default='Tool arguments to pass through to the MCP tool. Provide either a JSON object (recommended) or a JSON string.',
                    ),
                },
            },
            "required": ["tool_name", "tool_arguments"],
        },
    },
}


async def _call_mcp_stdio(
    command: str, args: list[str], env: dict[str, str], name: str, argv: dict[str, Any]
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


async def _call_mcp_http(url: str, name: str, argv: dict[str, Any]) -> str:
    mcp_url = url if url.endswith("/mcp") else url.rstrip("/") + "/mcp"
    try:
        async with streamable_http_client(mcp_url) as (read, write, session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, argv)
                return _format_result(result)
    except BaseExceptionGroup as eg:
        # NOTE: ExceptionGroup の内訳を返して原因を特定する（調査用）
        import traceback

        parts = [f"[Error] MCP http call failed: {str(eg)}"]
        for i, sub in enumerate(getattr(eg, "exceptions", []) or []):
            tb = "".join(traceback.format_exception(sub))
            parts.append(f"\n--- sub-exception {i} ({type(sub).__name__}) ---\n{tb}")
        return "\n".join(parts)
    except Exception as e:
        return f"[Error] MCP http call failed: {str(e)}"


def _format_result(result: Any) -> str:
    """Format MCP tool results for LLM.

    Return value policy:
    - Return a human-readable string.
    - If a file is saved locally or the server indicates a saved path, return: "[Saved] <path>".

    NOTE: Some skill pipelines may prefer structured JSON. If needed, wrap this function
    in a separate formatter rather than changing this return type.
    """

    # 0) Plain string
    if isinstance(result, str):
        return result

    # 1) Server-side saved file
    try:
        if isinstance(result, dict) and result.get("saved_path"):
            sp = str(result.get("saved_path"))
            return f"[Saved] {sp}"
    except Exception:
        pass

    def _save_download(filename: str, data: bytes) -> str:
        env_dir = env_get("UAGENT_DOWNLOAD_DIR")
        dl_dir = (
            os.path.abspath(os.path.expanduser(env_dir))
            if env_dir
            else os.path.abspath(os.path.join(os.getcwd(), "downloads"))
        )
        os.makedirs(dl_dir, exist_ok=True)

        base = os.path.basename(filename) or "download.bin"
        save_path = os.path.join(dl_dir, base)

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

    # 2) If server returned plain dict payload (base64 file)
    try:
        if (
            isinstance(result, dict)
            and result.get("data_base64")
            and result.get("filename")
        ):
            import base64

            raw_bytes = base64.b64decode(result.get("data_base64") or "")
            path = _save_download(str(result.get("filename")), raw_bytes)
            return f"[Saved] {path}"
    except Exception as e:
        return f"[Error] Failed to save returned file payload: {e}"

    output_parts: list[str] = []
    saved_path: str | None = None

    # 3) ToolResult-like with content blocks
    if hasattr(result, "content"):
        for content in result.content:
            # TextContent
            if hasattr(content, "text"):
                text = content.text
                if isinstance(text, str):
                    # If the text itself is JSON containing a file payload, save it.
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            if parsed.get("saved_path"):
                                sp = str(parsed.get("saved_path"))
                                saved_path = saved_path or sp
                                output_parts.append(f"[Saved] {sp}")
                                continue
                            if parsed.get("data_base64") and parsed.get("filename"):
                                import base64

                                raw_bytes = base64.b64decode(
                                    parsed.get("data_base64") or ""
                                )
                                path = _save_download(
                                    str(parsed.get("filename")), raw_bytes
                                )
                                saved_path = saved_path or path
                                output_parts.append(f"[Saved] {path}")
                                continue
                    except Exception:
                        pass

                output_parts.append(str(text))
                continue

            # ImageContent
            if hasattr(content, "data") and hasattr(content, "mimeType"):
                output_parts.append(f"[Binary/Image data: {content.mimeType}]")
                continue

            # Best-effort: resource/binary block with base64
            try:
                import base64

                b64 = getattr(content, "blob", None) or getattr(
                    content, "data_base64", None
                )
                fname = getattr(content, "filename", None) or getattr(
                    content, "name", None
                )

                res = getattr(content, "resource", None)
                if res is not None:
                    b64 = (
                        b64
                        or getattr(res, "blob", None)
                        or getattr(res, "data_base64", None)
                    )
                    fname = (
                        fname
                        or getattr(res, "filename", None)
                        or getattr(res, "name", None)
                    )

                if b64:
                    raw_bytes = base64.b64decode(b64)
                    path = _save_download(str(fname or "download.bin"), raw_bytes)
                    saved_path = saved_path or path
                    output_parts.append(f"[Saved] {path}")
                    continue

            except Exception as e:
                output_parts.append(f"[Warn] Unhandled binary-like content: {e}")
                continue

    if not output_parts:
        try:
            raw_text = json.dumps(result, default=lambda x: str(x), ensure_ascii=False)
        except Exception:
            raw_text = str(result)
        return _json_out(ok=True, text=raw_text, raw=result)

    return _json_out(ok=True, text="\n".join(output_parts), saved_path=saved_path)


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()

    server_name = str(args.get("server_name", "")).strip()
    url = args.get("url", "")
    name = args.get("tool_name")
    argv = args.get("args", {})

    # Allow tool_arguments to be provided as a JSON string (some proxies/LLMs serialize objects).
    if argv is None:
        argv = {}
    elif isinstance(argv, str):
        s = argv.strip()
        if not s:
            argv = {}
        else:
            try:
                argv = json.loads(s)

                # Some callers double-encode JSON (e.g., tool_arguments='"{}"').
                # Decode at most twice: str -> dict.
                if isinstance(argv, str):
                    s2 = argv.strip()
                    if s2:
                        argv = json.loads(s2)
            except Exception as e:
                return _json_out(
                    ok=False, text=f"Invalid tool_arguments JSON string: {e}"
                )

    if not isinstance(argv, dict):
        return _json_out(
            ok=False,
            text=f"tool_arguments must be an object/dict (or JSON string of an object). got={type(argv).__name__}",
        )

    if not name:
        return _("err.tool_name_required", default="Error: tool_name is required.")

    masked_argv = mask_values(argv)
    print(f"[MCP Call] Tool: {name}", file=sys.stderr)
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
                "MCP server is not configured. Please add a server via mcp_servers (action=add) (or create a config via mcp_servers (action=init_template)) "
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
        trunc = getattr(cb, "truncate_output", None)
        if callable(trunc):
            try:
                return trunc("handle_mcp_v2", result_text, 200_000)
            except TypeError:
                return trunc("handle_mcp_v2", result_text, limit=200_000)
        return result_text

    except Exception as e:
        return f"Unexpected error in run_tool: {str(e)}"
