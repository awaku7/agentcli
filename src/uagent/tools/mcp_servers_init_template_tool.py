from __future__ import annotations

import json
import os
from typing import Any, Dict

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        return "mcp_servers.json"


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
                    "description": "作成するパス。省略時は標準の場所（~/.scheck/mcps/mcp_servers.json 等）に作成します。",
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
    default_url = str(args.get("default_url", "")).strip() or ""
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
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"ERROR: 雛形作成に失敗しました: {type(e).__name__}: {e}"

    return f"OK: created template: {path!r} (default name={default_name!r})"
