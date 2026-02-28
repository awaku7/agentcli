# tools/db_query_tool.py
from __future__ import annotations

import sqlite3
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "db_query",
        "description": _(
            "tool.description",
            default=(
                "Execute an SQL query against an SQLite database and return the result. "
                "Only read-only operations (SELECT) and schema inspection (PRAGMA) are supported."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'db_query'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": _(
                        "param.db_path.description",
                        default="Path to the SQLite database file.",
                    ),
                },
                "sql": {
                    "type": "string",
                    "description": _(
                        "param.sql.description",
                        default="SQL to execute (must start with SELECT or PRAGMA).",
                    ),
                },
            },
            "required": ["db_path", "sql"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    db_path = str(args.get("db_path", "") or "").strip()
    sql = str(args.get("sql", "") or "").strip()

    if not db_path:
        raise ValueError("db_path is required")
    if not sql:
        raise ValueError("sql is required")

    # Safety: only allow SELECT / PRAGMA
    head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    if head not in ("SELECT", "PRAGMA"):
        raise ValueError("Only SELECT/PRAGMA are allowed")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        result_data = [dict(r) for r in rows]
        import json

        return json.dumps(result_data, ensure_ascii=False)
    finally:
        conn.close()
