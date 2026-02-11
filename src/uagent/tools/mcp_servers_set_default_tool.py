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
        "name": "mcp_servers_set_default",
        "description": (
            "mcp_servers.json のデフォルト接続先（mcp_servers[0]）を切り替えます。"
            "server_name に一致する要素を先頭へ移動します。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "デフォルトに設定したいサーバー名（mcp_servers[].name）",
                },
                "path": {
                    "type": "string",
                    "description": "サーバーリスト JSON のパス。省略時は標準の場所を参照します。",
                },
                "create_if_missing": {
                    "type": "boolean",
                    "description": "true の場合、ファイルが無いときは空の雛形を作ってから処理します（既定: true）",
                    "default": True,
                },
            },
            "required": ["server_name"],
        },
    },
}


def _load_config(
    path: str, create_if_missing: bool
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []

    if not os.path.exists(path):
        if create_if_missing:
            return {"mcp_servers": []}, [
                f"WARNING: {path!r} が存在しないため、新規作成対象として扱います"
            ]
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
        return data, warnings
    except Exception as e:
        return {"mcp_servers": []}, [
            f"ERROR: {path!r} の読み込みに失敗しました: {type(e).__name__}: {e}"
        ]


def run_tool(args: Dict[str, Any]) -> str:
    server_name = str(args.get("server_name", "")).strip()
    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    create_if_missing = bool(args.get("create_if_missing", True))

    if not server_name:
        return "Error: server_name is required."

    config, msgs = _load_config(path, create_if_missing)
    if any(m.startswith("ERROR:") for m in msgs):
        return "\n".join(msgs)

    servers = config.get("mcp_servers", [])
    if not servers:
        return "\n".join(
            msgs + ["ERROR: mcp_servers が空のため、default を切り替えできません"]
        )

    idx = None
    for i, s in enumerate(servers):
        if isinstance(s, dict) and s.get("name") == server_name:
            idx = i
            break

    if idx is None:
        return "\n".join(
            msgs + [f"ERROR: server_name={server_name!r} が見つかりません"]
        )

    if idx == 0:
        return "\n".join(msgs + [f"OK: 既に default です: {server_name!r}"])

    item = servers.pop(idx)
    servers.insert(0, item)
    config["mcp_servers"] = servers

    # 書き戻し（create_file を使い、.org バックアップを自動作成する）
    text = json.dumps(config, ensure_ascii=False, indent=2)
    try:
        try:
            from .create_file_tool import run_tool as create_file
        except ImportError:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return f"OK: default を切り替えました: {server_name!r} (Note: create_file_tool import failed, direct write used)"

        create_file(
            {"filename": path, "content": text, "encoding": "utf-8", "overwrite": True}
        )
    except Exception as e:
        return f"ERROR: 書き込みに失敗しました: {type(e).__name__}: {e}"

    return "\n".join(
        msgs
        + [
            f"OK: default を切り替えました: {server_name!r}",
            f"default url: {servers[0].get('url')!r}",
        ]
    )
