from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        import os

        return os.path.join(
            os.path.expanduser("~"), ".scheck", "mcps", "mcp_servers.json"
        )


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_add",
        "description": (
            "mcp_servers.json に MCP サーバー定義を追加（または上書き更新）します。"
            "既存 name がある場合は replace=true のときのみ上書きします。"
            "HTTP(SSE)接続の場合は url を、標準入出力(stdio)接続の場合は command と args を指定してください。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "サーバー名（mcp_servers[].name）",
                },
                "url": {
                    "type": "string",
                    "description": "MCP エンドポイント URL（例: REPLACE_ME (set your MCP server URL)）。stdio時は省略。",
                },
                "command": {
                    "type": "string",
                    "description": "実行するコマンド（例: npx, python, docker）。stdio接続用。",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "コマンド引数のリスト。stdio接続用。",
                },
                "env": {
                    "type": "object",
                    "description": "環境変数（辞書）。stdio接続用。",
                },
                "transport": {
                    "type": "string",
                    "description": "transport（参考情報）。streamable-http または stdio。",
                    "default": "streamable-http",
                },
                "path": {
                    "type": "string",
                    "description": "サーバーリスト JSON のパス。省略時は標準の場所を参照します。",
                },
                "set_default": {
                    "type": "boolean",
                    "description": "true の場合、追加/更新後にそのサーバーをデフォルト（先頭）にします（既定: false）",
                    "default": False,
                },
                "replace": {
                    "type": "boolean",
                    "description": "true の場合、同名が存在するときに上書き更新します（既定: false）",
                    "default": False,
                },
                "create_if_missing": {
                    "type": "boolean",
                    "description": "true の場合、ファイルが無いときは新規作成します（既定: true）",
                    "default": True,
                },
            },
            "required": ["name"],
        },
    },
}


def _load_config(
    path: str, create_if_missing: bool
) -> Tuple[Dict[str, Any], List[str]]:
    if not os.path.exists(path):
        if create_if_missing:
            return {"mcp_servers": []}, [
                f"WARNING: {path!r} が存在しないため新規作成します"
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
        return data, []
    except Exception as e:
        return {"mcp_servers": []}, [
            f"ERROR: {path!r} の読み込みに失敗しました: {type(e).__name__}: {e}"
        ]


def run_tool(args: Dict[str, Any]) -> str:
    name = str(args.get("name", "")).strip()
    url = str(args.get("url", "")).strip()
    command = str(args.get("command", "")).strip()
    cmd_args = args.get("args") or []
    env = args.get("env") or {}

    transport_arg = str(args.get("transport", "")).strip()

    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    set_default = bool(args.get("set_default", False))
    replace = bool(args.get("replace", False))
    create_if_missing = bool(args.get("create_if_missing", True))

    if not name:
        return "Error: name is required."

    if not url and not command:
        return "Error: url or command is required."

    config, msgs = _load_config(path, create_if_missing)
    if any(m.startswith("ERROR:") for m in msgs):
        return "\n".join(msgs)

    servers = config.get("mcp_servers", [])

    existing_idx = None
    for i, s in enumerate(servers):
        if isinstance(s, dict) and s.get("name") == name:
            existing_idx = i
            break

    item = {"name": name}
    if url:
        item["url"] = url
        item["transport"] = transport_arg or "streamable-http"
    else:
        item["command"] = command
        item["args"] = cmd_args
        if env:
            item["env"] = env
        item["transport"] = transport_arg or "stdio"

    if existing_idx is None:
        if set_default:
            servers.insert(0, item)
        else:
            servers.append(item)
        action = "added"
    else:
        if not replace:
            return "\n".join(
                msgs
                + [f"ERROR: name={name!r} は既に存在します（replace=true で上書き）"]
            )

        # 上書き
        if set_default:
            # 既存を削除して先頭に
            servers.pop(existing_idx)
            servers.insert(0, item)
        else:
            servers[existing_idx] = item
        action = "replaced"

    config["mcp_servers"] = servers

    # 書き戻し
    text = json.dumps(config, ensure_ascii=False, indent=2)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        return f"ERROR: 書き込みに失敗しました: {type(e).__name__}: {e}"

    default_info = "<none>"
    if servers:
        s0 = servers[0]
        if s0.get("url"):
            default_info = f"name={s0.get('name')!r} url={s0.get('url')!r}"
        else:
            default_info = f"name={s0.get('name')!r} command={s0.get('command')!r}"

    return "\n".join(
        msgs
        + [
            f"OK: {action}: name={name!r}",
            f"default: {default_info}",
            f"count: {len(servers)}",
        ]
    )
