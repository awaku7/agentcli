"""SQLite persistence for personal and shared long-term memory."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "created_at REAL NOT NULL, note TEXT NOT NULL)"
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def append(self, note: str) -> None:
        self.db.execute(
            "INSERT INTO memories(created_at, note) VALUES (?, ?)",
            (time.time(), note),
        )
        self.db.commit()

    def records(self) -> list[dict[str, object]]:
        rows = self.db.execute(
            "SELECT id, created_at, note FROM memories ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def replace(self, records: list[dict[str, object]]) -> None:
        self.db.execute("DELETE FROM memories")
        self.db.executemany(
            "INSERT INTO memories(created_at, note) VALUES (?, ?)",
            [(float(row.get("ts", time.time())), str(row.get("note", "")))
             for row in records if str(row.get("note", ""))],
        )
        self.db.commit()

    def delete(self, index: int) -> bool:
        rows = self.db.execute("SELECT id FROM memories ORDER BY id").fetchall()
        if index < 0 or index >= len(rows):
            return False
        self.db.execute("DELETE FROM memories WHERE id = ?", (rows[index]["id"],))
        self.db.commit()
        return True


def open_memory_store(path: str | Path) -> MemoryStore:
    return MemoryStore(path)
