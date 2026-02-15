from __future__ import annotations

import json
import os
from typing import Any, Dict

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        import os

        env_path = os.environ.get("UAGENT_MCP_CONFIG")
        if env_path:
            return os.path.abspath(os.path.expanduser(env_path))

        try:
            from uagent.utils.paths import get_mcp_servers_json_path

            return str(get_mcp_servers_json_path())
        except Exception:
            p_new = os.path.join(os.path.expanduser("~"), ".uag", "mcps", "mcp_servers.json")
            if os.path.exists(p_new):
                return p_new
            return os.path.join(
                os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json"
            )


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_init_template",
        "description": (
            "mcp_servers.json が存在しない場合に、雛形ファイルを作成します。"
            "存在する場合はエラーを返します（上書きはしません）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "作成するパス。省略時は標準の場所（<state>/mcps/mcp_servers.json。既定: ~/.uag（旧: ~/.scheck）/mcps/mcp_servers.json）に作成します。",
                },
                "default_name": {
                    "type": "string",
                    "description": "デフォルトのサーバー名。既定: bluesky-local",
                    "default": "bluesky-local",
                },
                "default_url": {
                    "type": "string",
                    "description": "デフォルトの URL。既定: REPLACE_ME (set your MCP server URL)",
                    "default": "",
                },
                "default_transport": {
                    "type": "string",
                    "description": "デフォルトの transport（参考情報）。既定: streamable-http",
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
    default_url = (
        str(args.get("default_url", "")).strip()
        or ""
    )
    default_transport = (
        str(args.get("default_transport", "streamable-http")).strip()
        or "streamable-http"
    )

    if os.path.exists(path):
        return f"Error: {path!r} は既に存在します（このツールは上書きしません）"

    data: Dict[str, Any] = {
        "mcp_servers": [
            {
                "name": default_name,
                "url": default_url,
                "transport": default_transport,
            }
        ]
    }

    # 新規作成のみ（overwrite=False）
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        try:
            from .create_file_tool import run_tool as create_file
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"OK: created template: {path!r} (Note: create_file_tool import failed, direct write used)"

        create_file(
            {
                "filename": path,
                "content": content,
                "encoding": "utf-8",
                "overwrite": False,
            }
        )
    except Exception as e:
        return f"ERROR: 雛形作成に失敗しました: {type(e).__name__}: {e}"

    return f"OK: created template: {path!r} (default name={default_name!r})"
