# tools/db_query_tool.py
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "devel",
    "x_parallel_safe": True,
    "function": {
        "name": "db_query",
        "description": _(
            "tool.description",
            default="Execute an SQL query against an SQLite database and return the result. Only read-only operations (SELECT) and schema inspection (PRAGMA) are suppor...",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "db_query",
                "db query",
                "sql",
                "database",
                "sqlite",
                "query",
            ],
        ),
        "x_search_terms_en": [
            "db_query",
            "db query",
            "sql",
            "database",
            "sqlite",
            "query",
        ],
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


def run_tool(args: dict[str, Any]) -> str:
    db_path = str(args.get("db_path", "") or "").strip()
    sql = str(args.get("sql", "") or "").strip()

    if not db_path:
        raise ValueError("db_path is required")
    if not sql:
        raise ValueError("sql is required")

    # Safety: only allow SELECT / PRAGMA
    head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    if head not in ("SELECT", "PRAGMA"):
        return _(
            "err.readonly",
            default="[db_query error] Only SELECT and PRAGMA statements are allowed.",
        )

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)

        rows = [dict(row) for row in cursor.fetchall()]
        colnames = [desc[0] for desc in cursor.description] if cursor.description else []

        conn.close()

        return _(
            "msg.result",
            default="[db_query]\nrows={rows}\ncolumns={cols}",
        ).format(rows=len(rows), cols=", ".join(colnames)) + "\n" + "\n".join(
            json.dumps(r, ensure_ascii=False, default=str) for r in rows
        )
    except Exception as e:
        return f"[db_query error] {type(e).__name__}: {e}"
