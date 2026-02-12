from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        return "mcp_servers.json"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_remove",
        "description": (
            "mcp_servers.json から MCP サーバー定義を削除します。"
            "name 指定で削除するか、index 指定で削除できます（どちらか必須）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "削除対象のサーバー名（mcp_servers[].name）",
                },
                "index": {
                    "type": "integer",
                    "description": "削除対象のインデックス（mcp_servers[n]）。name と同時指定時は index を優先します。",
                },
                "path": {
                    "type": "string",
                    "description": "サーバーリスト JSON のパス。省略時は標準の場所を参照します。",
                },
                "require_nonempty": {
                    "type": "boolean",
                    "description": "true の場合、削除後に空になる操作を禁止します（既定: false）",
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _load_config(path: str) -> Tuple[Dict[str, Any], List[str]]:
    if not os.path.exists(path):
        return {"mcp_servers": []}, [f"ERROR: {path!r} が存在しません"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"mcp_servers": []}, ["ERROR: ルートが dict ではありません"]
        if "mcp_servers" not in data:
            data["mcp_servers"] = []
        if not isinstance(data.get("mcp_servers"), list):
            return {"mcp_servers": []}, ["ERROR: 'mcp_servers' が list ではありません"]
        return data, []
    except Exception as e:
        return {"mcp_servers": []}, [
            f"ERROR: {path!r} の読み込みに失敗しました: {type(e).__name__}: {e}"
        ]


def run_tool(args: Dict[str, Any]) -> str:
    name = args.get("name")
    index = args.get("index")
    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    require_nonempty = bool(args.get("require_nonempty", False))

    if index is None and (not isinstance(name, str) or not name.strip()):
        return "Error: name または index のどちらかを指定してください。"

    config, msgs = _load_config(path)
    if any(m.startswith("ERROR:") for m in msgs):
        return "\n".join(msgs)

    servers = config.get("mcp_servers", [])
    if not servers:
        return "ERROR: mcp_servers が空です"

    removed = None
    removed_idx = None

    if index is not None:
        try:
            idx = int(index)
        except Exception:
            return "Error: index は整数で指定してください"
        if idx < 0 or idx >= len(servers):
            return f"Error: index out of range: {idx}"
        removed = servers.pop(idx)
        removed_idx = idx
    else:
        target = str(name).strip()
        for i, s in enumerate(servers):
            if isinstance(s, dict) and s.get("name") == target:
                removed = servers.pop(i)
                removed_idx = i
                break
        if removed is None:
            return f"Error: name={target!r} が見つかりません"

    if require_nonempty and not servers:
        return "Error: require_nonempty=true のため、削除後に空になる操作は禁止です"

    config["mcp_servers"] = servers

    text = json.dumps(config, ensure_ascii=False, indent=2)
    try:
        try:
            from .create_file_tool import run_tool as create_file
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

            r_name = removed.get("name") if isinstance(removed, dict) else None
            return (
                f"OK: removed index={removed_idx} name={r_name!r} "
                "(Note: create_file_tool import failed, direct write used)"
            )

        create_file(
            {"filename": path, "content": text, "encoding": "utf-8", "overwrite": True}
        )
    except Exception as e:
        return f"ERROR: 書き込みに失敗しました: {type(e).__name__}: {e}"

    default_info = "<none>"
    if servers:
        default_info = f"name={servers[0].get('name')!r} url={servers[0].get('url')!r}"

    r_name = removed.get("name") if isinstance(removed, dict) else None

    return "\n".join(
        [
            f"OK: removed index={removed_idx} name={r_name!r}",
            f"default: {default_info}",
            f"count: {len(servers)}",
        ]
    )
