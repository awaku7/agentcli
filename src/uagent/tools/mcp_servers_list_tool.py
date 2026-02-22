from __future__ import annotations
from .i18n_helper import make_tool_translator
_ = make_tool_translator(__file__)


import json
import os
from typing import Any, Dict, List, Tuple

try:
    from .mcp_servers_shared import get_default_mcp_config_path
except ImportError:

    def get_default_mcp_config_path():
        return "mcp_servers.json"


from .context import get_callbacks

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mcp_servers_list",
        "description": (
            "mcp_servers.json の MCP サーバー定義を一覧表示します。"
            "mcp_tools_list(url省略) が参照する接続先候補を可視化するためのツールです。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "サーバーリスト JSON のパス。省略時は標準の場所を参照します。",
                },
                "pretty": {
                    "type": "boolean",
                    "description": "true の場合は JSON を整形して返します（既定: true）",
                    "default": True,
                },
                "validate": {
                    "type": "boolean",
                    "description": (
                        "true の場合は簡易バリデーション（必須キー/型/name重複/空URL等）を行い、"
                        "警告を表示します（既定: true）"
                    ),
                    "default": True,
                },
                "default_only": {
                    "type": "boolean",
                    "description": "true の場合はデフォルト（mcp_servers[0]）のみ返します（既定: false）",
                    "default": False,
                },
                "raw": {
                    "type": "boolean",
                    "description": (
                        "true の場合は人間向けの整形テキストを付けず、JSON 文字列のみ返します（既定: false）"
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _load_config(path: str) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []

    if not os.path.exists(path):
        return {"mcp_servers": []}, [
            f"WARNING: {path!r} が存在しません（空リストとして扱います）"
        ]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            warnings.append("WARNING: ルートが dict ではありません")
            return {"mcp_servers": []}, warnings
        if "mcp_servers" not in data:
            warnings.append(
                "WARNING: 'mcp_servers' キーがありません（空リストとして扱います）"
            )
            data["mcp_servers"] = []
        if not isinstance(data.get("mcp_servers"), list):
            warnings.append(
                "WARNING: 'mcp_servers' が list ではありません（空リストとして扱います）"
            )
            data["mcp_servers"] = []
        return data, warnings
    except Exception as e:
        return {"mcp_servers": []}, [
            f"WARNING: {path!r} の読み込みに失敗しました: {type(e).__name__}: {e}"
        ]


def _validate_servers(servers: List[Any]) -> List[str]:
    warnings: List[str] = []

    seen_names: Dict[str, int] = {}
    for idx, s in enumerate(servers):
        if not isinstance(s, dict):
            warnings.append(f"WARNING: mcp_servers[{idx}] が dict ではありません")
            continue

        name = s.get("name")
        url = s.get("url")

        if not isinstance(name, str) or not name.strip():
            warnings.append(f"WARNING: mcp_servers[{idx}].name が未設定/空です")
        else:
            seen_names[name] = seen_names.get(name, 0) + 1

        if not isinstance(url, str) or not url.strip():
            warnings.append(f"WARNING: mcp_servers[{idx}].url が未設定/空です")
        else:
            if not url.rstrip().endswith("/mcp"):
                warnings.append(
                    f"WARNING: mcp_servers[{idx}].url={url!r} は '/mcp' で終わっていません。"
                    "（handle_mcp_v2 / mcp_tools_list は自動補完しますが、明示推奨です）"
                )

    for n, c in seen_names.items():
        if c > 1:
            warnings.append(f"WARNING: name={n!r} が重複しています（{c}件）")

    return warnings


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    pretty = bool(args.get("pretty", True))
    validate = bool(args.get("validate", True))
    default_only = bool(args.get("default_only", False))
    raw = bool(args.get("raw", False))

    config, load_warnings = _load_config(path)
    servers = config.get("mcp_servers", [])

    warnings: List[str] = []
    warnings.extend(load_warnings)
    if validate:
        warnings.extend(_validate_servers(servers))

    # 表示対象
    view_servers = servers[:1] if default_only else servers

    out_obj: Dict[str, Any] = {
        "path": path,
        "default_index": 0,
        "count": len(servers),
        "default": servers[0] if servers else None,
        "servers": view_servers,
        "warnings": warnings,
    }

    if raw:
        return json.dumps(out_obj, ensure_ascii=False, indent=2 if pretty else None)

    lines: List[str] = []
    lines.append(f"mcp_servers.json path: {path}")
    lines.append(f"servers count: {len(servers)}")
    if servers:
        d = servers[0]
        lines.append(
            f"default (mcp_servers[0]): name={d.get('name')!r} url={d.get('url')!r}"
        )
    else:
        lines.append("default (mcp_servers[0]): <none>")

    lines.append("")
    lines.append("servers:")
    for i, s in enumerate(view_servers):
        if isinstance(s, dict):
            lines.append(
                f"- [{i}] name={s.get('name')!r} url={s.get('url')!r} transport={s.get('transport')!r}"
            )
        else:
            lines.append(f"- [{i}] <invalid item type: {type(s).__name__}>")

    if warnings:
        lines.append("")
        lines.append("warnings:")
        for w in warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("raw JSON:")
    lines.append(json.dumps(out_obj, ensure_ascii=False, indent=2 if pretty else None))

    return cb.truncate_output("mcp_servers_list", "\n".join(lines), limit=200_000)
