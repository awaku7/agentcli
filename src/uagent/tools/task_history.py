"""Durable SQLite history for resumable agent tasks."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL DEFAULT '',
            instruction TEXT NOT NULL DEFAULT '',
            state_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL
        )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS task_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            state_json TEXT,
            created_at TEXT NOT NULL
        )""")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_conversation " "ON tasks(conversation_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_task "
        "ON task_events(task_id, event_id)"
    )
    return conn


def save_task(
    db_path: Path,
    state: dict[str, Any],
    event_type: str = "snapshot",
    message: str = "",
) -> None:
    task_id = str(state.get("batch_id", ""))
    if not task_id:
        return
    state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
    updated_at = str(state.get("updated_at") or state.get("last_updated") or "")
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO tasks(task_id, conversation_id, instruction, state_json, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(task_id) DO UPDATE SET
                 conversation_id=excluded.conversation_id,
                 instruction=excluded.instruction,
                 state_json=excluded.state_json,
                 status=excluded.status,
                 updated_at=excluded.updated_at""",
            (
                task_id,
                str(state.get("conversation_id", "")),
                str(state.get("instructions", "")),
                state_json,
                str(state.get("status", "active")),
                updated_at,
            ),
        )
        conn.execute(
            "INSERT INTO task_events(task_id,event_type,message,state_json,created_at) "
            "VALUES (?,?,?,?,?)",
            (task_id, event_type, message, state_json, updated_at),
        )
        conn.commit()
    finally:
        conn.close()


def list_tasks(db_path: Path) -> list[dict[str, Any]]:
    """Return the latest persisted state for every task."""
    if not db_path.exists():
        return []
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT state_json FROM tasks ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()
    result: list[dict[str, Any]] = []
    for (state_json,) in rows:
        try:
            state = json.loads(state_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(state, dict):
            result.append(state)
    return result


def load_task(db_path: Path, task_id: str) -> dict[str, Any] | None:
    if not db_path.exists():
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT state_json FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    try:
        value = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
