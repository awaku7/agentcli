# tools/get_geoip_tool.py
from __future__ import annotations

import json
from typing import Any, Dict

from .fetch_url_tool import run_tool as fetch_url_run

BUSY_LABEL = True
STATUS_LABEL = "tool:get_geoip"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_geoip",
        "description": (
            "グローバルIPに基づいて現在位置をざっくり推定できます。"
            "VPN/プロキシ利用時は推定が外れることがあります。\n\n"
            "【利用方針】\n"
            "- ユーザーの場所（都市/地域/国など）が必要な質問に答えるときは、必ずこの get_geoip ツールを使って推定位置を取得してください。\n"
            "- ただし、ユーザーが場所を明示している場合はそれを優先し、get_geoip は不要です"
        ),
        "system_prompt": """このツールは次の目的で使われます: 出力形式。'text' か 'json'。既定は 'text'。
- 現在のユーザーの場所がわからない場合に利用します
""",
        "parameters": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "出力形式。'text' か 'json'。既定は 'text'。",
                    "enum": ["text", "json"],
                },
                "require_consent": {
                    "type": "boolean",
                    "description": "true の場合、外部サービスへアクセスする前に同意が必要です。既定は true。",
                },
            },
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    out_format = (args.get("format") or "text").strip().lower()
    if out_format not in ("text", "json"):
        return "[get_geoip error] format は 'text' または 'json' を指定してください"

    # 同意処理は廃止（UAGENT_GEOIP_CONSENT を含む環境変数参照は行わない）
    # require_consent パラメータは互換のために受け付けるが無視する。

    # ipinfo の JSON を取得
    raw = fetch_url_run({"url": "https://ipinfo.io/json"})

    # fetch_url のメタ行を除去して JSON 部分を抽出
    idx = raw.find("\n{")
    json_text = raw[idx + 1 :] if idx >= 0 else raw

    try:
        data = json.loads(json_text)
    except Exception as e:
        return (
            "[get_geoip error] ipinfo.io の応答を JSON として解析できませんでした: "
            + repr(e)
            + "\n\n"
            + raw
        )

    # 最低限のフィールドを整形
    result = {
        "ip": data.get("ip"),
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country"),
        "loc": data.get("loc"),
        "org": data.get("org"),
        "postal": data.get("postal"),
        "timezone": data.get("timezone"),
    }

    if out_format == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)

    lines = [
        "[get_geoip] ipinfo.io によるIPベース位置推定（ざっくり）",
        f"IP: {result.get('ip')}",
        f"国: {result.get('country')}",
        f"地域: {result.get('region')}",
        f"都市: {result.get('city')}",
        f"座標(推定): {result.get('loc')}",
        f"タイムゾーン: {result.get('timezone')}",
        f"回線組織: {result.get('org')}",
        "※VPN/プロキシ/モバイル回線では外れることがあります",
    ]
    return "\n".join(lines)
