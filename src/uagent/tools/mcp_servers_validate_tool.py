from __future__ import annotations

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
        "name": "mcp_servers_validate",
        "description": (
            "mcp_servers.json の内容を検証し、警告/エラーを返します。"
            "（必須キー/型/name重複/空URL/'/mcp'末尾 など）"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "サーバーリスト JSON のパス。省略時は標準の場所を参照します。",
                },
                "fail_on_warning": {
                    "type": "boolean",
                    "description": "true の場合、警告が1件でもあれば overall=FAIL を返します（既定: false）",
                    "default": False,
                },
                "pretty": {
                    "type": "boolean",
                    "description": "true の場合は JSON を整形して返します（既定: true）",
                    "default": True,
                },
            },
            "required": [],
        },
    },
}


def _load_config(path: str) -> Tuple[Dict[str, Any], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    if not os.path.exists(path):
        errors.append(f"ERROR: {path!r} が存在しません")
        return {"mcp_servers": []}, warnings, errors

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        errors.append(
            f"ERROR: {path!r} の読み込みに失敗しました: {type(e).__name__}: {e}"
        )
        return {"mcp_servers": []}, warnings, errors

    if not isinstance(data, dict):
        errors.append("ERROR: ルートが dict ではありません")
        return {"mcp_servers": []}, warnings, errors

    servers = data.get("mcp_servers")
    if servers is None:
        warnings.append("WARNING: 'mcp_servers' キーがありません")
        servers = []
    if not isinstance(servers, list):
        errors.append("ERROR: 'mcp_servers' が list ではありません")
        servers = []

    data["mcp_servers"] = servers
    return data, warnings, errors


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    path = args.get("path")
    if not path:
        path = get_default_mcp_config_path()
    else:
        path = str(path)
    fail_on_warning = bool(args.get("fail_on_warning", False))
    pretty = bool(args.get("pretty", True))

    config, warnings, errors = _load_config(path)
    servers: List[Any] = config.get("mcp_servers", [])

    seen_names: Dict[str, int] = {}

    for idx, s in enumerate(servers):
        if not isinstance(s, dict):
            errors.append(f"ERROR: mcp_servers[{idx}] が dict ではありません")
            continue

        name = s.get("name")
        url = s.get("url")

        if not isinstance(name, str) or not name.strip():
            errors.append(f"ERROR: mcp_servers[{idx}].name が未設定/空です")
        else:
            seen_names[name] = seen_names.get(name, 0) + 1

        if not isinstance(url, str) or not url.strip():
            errors.append(f"ERROR: mcp_servers[{idx}].url が未設定/空です")
        else:
            if not url.rstrip().endswith("/mcp"):
                warnings.append(
                    f"WARNING: mcp_servers[{idx}].url={url!r} は '/mcp' で終わっていません。"
                    "（handle_mcp_v2 / mcp_tools_list は自動補完しますが、明示推奨です）"
                )

    for n, c in seen_names.items():
        if c > 1:
            errors.append(f"ERROR: name={n!r} が重複しています（{c}件）")

    overall = "OK"
    if errors:
        overall = "FAIL"
    elif warnings and fail_on_warning:
        overall = "FAIL"

    out = {
        "path": path,
        "overall": overall,
        "count": len(servers),
        "warnings": warnings,
        "errors": errors,
    }

    return cb.truncate_output(
        "mcp_servers_validate",
        json.dumps(out, ensure_ascii=False, indent=2 if pretty else None),
        limit=200_000,
    )
