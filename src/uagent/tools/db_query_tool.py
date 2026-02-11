# tools/db_query_tool.py
import sqlite3
import json
import os
from typing import Any, Dict

BUSY_LABEL = True
STATUS_LABEL = "tool:db_query"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "db_query",
        "description": "SQLiteデータベースに対してSQLクエリを実行し、結果を取得します。データの読み取り（SELECT）およびスキーマ確認（PRAGMA）のみ対応しています。",
        "system_prompt": """このツールは次の目的で使われます: SQLiteデータベースに対してSQLクエリを実行し、結果を取得します。データの読み取り（SELECT）およびスキーマ確認（PRAGMA）のみ対応しています。""",
        "parameters": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "SQLiteデータベースファイルのパス。",
                },
                "sql": {
                    "type": "string",
                    "description": "実行するSQL文（SELECT または PRAGMA で始まること）。",
                },
            },
            "required": ["db_path", "sql"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    """
    SQLiteクエリ実行ツール
    """
    db_path = args.get("db_path", "").strip()
    sql = args.get("sql", "").strip()

    if not db_path:
        return "[db_query error] db_path が指定されていません。"
    if not sql:
        return "[db_query error] sql が指定されていません。"

    if not os.path.exists(db_path):
        return f"[db_query error] データベースファイルが見つかりません: {db_path}"

    # 簡易的な安全チェック: 先頭が SELECT / PRAGMA / EXPLAIN であること
    upper_sql = sql.upper().lstrip()
    allowed_prefixes = ("SELECT", "PRAGMA", "EXPLAIN")
    if not any(upper_sql.startswith(p) for p in allowed_prefixes):
        # WITH ... SELECT ... のようなケースも許容したい場合は WITH も追加する必要があるが、
        # いったん安全側に倒して拒否する
        if upper_sql.startswith("WITH"):
            pass  # WITH 句は許可してもよいが、後続が DELETE な可能性もあるのでパースが面倒
            # ここでは簡易的に SELECT / PRAGMA のみとする

        return (
            "[db_query error] 安全のため、実行できるSQLは SELECT / PRAGMA / EXPLAIN のみに制限されています。\n"
            "更新系のクエリは実行できません。"
        )

    try:
        # 読み取り専用で開く (URI mode)
        # WindowsのパスだとURI変換が面倒なので、通常の接続後に readonly を期待するが、
        # sqlite3.connect はデフォルトで読み書き可能。
        # URI指定: f"file:{db_path}?mode=ro" が確実だが、パス形式の扱いに注意が必要。
        # ここではシンプルに connect して、SQLチェックでガードする方針とする。

        conn = sqlite3.connect(db_path)
        try:
            # Row factory を設定してカラム名でアクセス可能に
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(sql)
            rows = cursor.fetchall()

            # 結果を辞書のリストに変換
            result_data = [dict(row) for row in rows]

            # 件数が多い場合は要約する仕組みがあってもいいが、
            # Agentが全量を知りたい場合もあるので、いったんJSONdumpする。
            # ただし巨大すぎる場合は制限が必要。
            json_str = json.dumps(result_data, ensure_ascii=False, default=str)

            res_body = f"[db_query] Result:\n{json_str}"
            MAX_LEN = 10000
            if len(json_str) > MAX_LEN:
                suffix = f"... (truncated, total {len(result_data)} rows)"
                res_body = (
                    f"[db_query] Result (truncated):\n{json_str[:MAX_LEN]}\n{suffix}"
                )

            return res_body

        finally:
            conn.close()

    except sqlite3.Error as e:
        return f"[db_query error] SQL execution failed: {e}"
    except Exception as e:
        return f"[db_query error] Unexpected error: {e}"
