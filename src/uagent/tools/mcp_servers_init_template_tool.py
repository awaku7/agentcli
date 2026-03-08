from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


import json
import os
from ..env_utils import env_get
from typing import Any, Dict

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
        "name": "mcp_servers_init_template",
        "description": _(
            "tool.description",
            default="Creates a template file if mcp_servers.json does not exist. Returns an error if it already exists (does not overwrite).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="The path to create. Defaults to the standard location (~/.uag/mcps/mcp_servers.json) if omitted.",
                    ),
                },
                "default_name": {
                    "type": "string",
                    "description": _(
                        "param.default_name.description",
                        default="Default server name. Default is 'bluesky-local'.",
                    ),
                    "default": "bluesky-local",
                },
                "default_url": {
                    "type": "string",
                    "description": _(
                        "param.default_url.description",
                        default="Default URL. Default is 'REPLACE_ME (set your MCP server URL)'.",
                    ),
                    "default": "",
                },
                "default_transport": {
                    "type": "string",
                    "description": _(
                        "param.default_transport.description",
                        default="Default transport (informational). Default is 'streamable-http'.",
                    ),
                    "default": "streamable-http",
                },
            },
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    default_name = (
        str(args.get("default_name", "bluesky-local")).strip() or "bluesky-local"
    )
    default_url = str(args.get("default_url", "")).strip() or ""
    default_transport = (
        str(args.get("default_transport", "streamable-http")).strip()
        or "streamable-http"
    )

    if os.path.exists(path):
        return _(
            "err.exists",
            default="Error: {path!r} already exists (this tool will not overwrite).",
        ).format(path=path)

    data: Dict[str, Any] = {
        "mcp_servers": [
            {
                "name": default_name,
                "url": default_url,
                "transport": default_transport,
            }
        ]
    }

    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            from .create_file_tool import run_tool as create_file
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return _(
                "out.ok",
                default="OK: created template: {path!r} (default name={name!r})",
            ).format(path=path, name=default_name)

        create_file(
            {
                "filename": path,
                "content": content,
                "encoding": "utf-8",
                "overwrite": False,
            }
        )
    except Exception as e:
        return _("err.fail", default="ERROR: Failed to create template: {err}").format(
            err=e
        )

    return _(
        "out.ok", default="OK: created template: {path!r} (default name={name!r})"
    ).format(path=path, name=default_name)
