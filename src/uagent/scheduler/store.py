from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..utils.paths import get_schedules_json_path
from .models import ScheduleItem, format_iso_datetime, utc_now

_LOCK = threading.RLock()
_SQLITE_MAGIC = b"SQLite format 3\x00"


class SchedulerStore:
    """SQLite-backed scheduler definitions with cross-process claims.

    Legacy JSON files are imported once and renamed with a ``.legacy`` suffix.
    The public methods remain compatible with the former JSON store.
    """

    def __init__(self, json_path: str | Path | None = None) -> None:
        self.path = Path(json_path or get_schedules_json_path())
        self._prepare_path()
        self._initialize()

    def _prepare_path(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        with self.path.open("rb") as stream:
            if stream.read(len(_SQLITE_MAGIC)) == _SQLITE_MAGIC:
                return
        legacy_path = self.path.with_name(self.path.name + ".legacy")
        if legacy_path.exists():
            legacy_path = self.path.with_name(
                f"{self.path.name}.legacy.{int(time.time())}"
            )
        os.replace(self.path, legacy_path)
        try:
            raw = json.loads(legacy_path.read_text(encoding="utf-8"))
            rows = raw.get("items", []) if isinstance(raw, dict) else raw
            if not isinstance(rows, list):
                rows = []
        except Exception:
            rows = []
        self._legacy_rows = [row for row in rows if isinstance(row, dict)]

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.path), timeout=30.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        try:
            mode = str(db.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode == "wal":
                db.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.DatabaseError:
            # Read-only or unsupported filesystems retain SQLite's safe default.
            db.execute("PRAGMA journal_mode=DELETE")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS schedules ("
                "id TEXT PRIMARY KEY, type TEXT NOT NULL, at TEXT NOT NULL, "
                "message TEXT NOT NULL, llm_prompt TEXT NOT NULL, interval_sec INTEGER NOT NULL, "
                "retry_limit INTEGER NOT NULL, retry_backoff_sec INTEGER NOT NULL, "
                "timeout_sec INTEGER NOT NULL, required_tools TEXT NOT NULL, "
                "execution_mode TEXT NOT NULL, target_tool TEXT NOT NULL, target_args TEXT NOT NULL, "
                "owner_instance_id TEXT NOT NULL DEFAULT '', session_id TEXT NOT NULL DEFAULT '', "
                "enabled INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                "claim_owner TEXT NOT NULL DEFAULT '', claim_until REAL NOT NULL DEFAULT 0"
                ")"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS scheduler_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "event_key TEXT NOT NULL UNIQUE, "
                "schedule_id TEXT NOT NULL, run_id TEXT NOT NULL, "
                "target_instance_id TEXT NOT NULL DEFAULT '', "
                "payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', "
                "attempt_count INTEGER NOT NULL DEFAULT 0, "
                "available_at REAL NOT NULL DEFAULT 0, "
                "claim_owner TEXT NOT NULL DEFAULT '', claim_until REAL NOT NULL DEFAULT 0, "
                "last_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, "
                "delivered_at TEXT NOT NULL DEFAULT ''"
                ")"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scheduler_events_pending "
                "ON scheduler_events(status, available_at, target_instance_id, id)"
            )
            rows = getattr(self, "_legacy_rows", [])
            if rows:
                self._replace_rows(db, [ScheduleItem.from_dict(row) for row in rows])
                del self._legacy_rows

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> ScheduleItem:
        return ScheduleItem.from_dict(
            {
                "id": row["id"],
                "type": row["type"],
                "at": row["at"],
                "message": row["message"],
                "llm_prompt": row["llm_prompt"],
                "interval_sec": row["interval_sec"],
                "retry_limit": row["retry_limit"],
                "retry_backoff_sec": row["retry_backoff_sec"],
                "timeout_sec": row["timeout_sec"],
                "required_tools": json.loads(row["required_tools"] or "[]"),
                "execution_mode": row["execution_mode"],
                "target_tool": row["target_tool"],
                "target_args": json.loads(row["target_args"] or "{}"),
                "owner_instance_id": row["owner_instance_id"],
                "session_id": row["session_id"],
                "enabled": bool(row["enabled"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    @staticmethod
    def _params(item: ScheduleItem) -> tuple[Any, ...]:
        normalized = item.normalized()
        return (
            normalized.id,
            normalized.type,
            normalized.at,
            normalized.message,
            normalized.llm_prompt,
            normalized.interval_sec,
            normalized.retry_limit,
            normalized.retry_backoff_sec,
            normalized.timeout_sec,
            json.dumps(normalized.required_tools, ensure_ascii=False),
            normalized.execution_mode,
            normalized.target_tool,
            json.dumps(normalized.target_args, ensure_ascii=False),
            normalized.owner_instance_id,
            normalized.session_id,
            int(normalized.enabled),
            normalized.created_at,
            normalized.updated_at,
        )

    @classmethod
    def _upsert(cls, db: sqlite3.Connection, item: ScheduleItem) -> None:
        db.execute(
            "INSERT INTO schedules (id,type,at,message,llm_prompt,interval_sec,retry_limit,"
            "retry_backoff_sec,timeout_sec,required_tools,execution_mode,target_tool,target_args,"
            "owner_instance_id,session_id,enabled,created_at,updated_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET type=excluded.type, at=excluded.at, "
            "message=excluded.message, llm_prompt=excluded.llm_prompt, interval_sec=excluded.interval_sec, "
            "retry_limit=excluded.retry_limit, retry_backoff_sec=excluded.retry_backoff_sec, "
            "timeout_sec=excluded.timeout_sec, required_tools=excluded.required_tools, "
            "execution_mode=excluded.execution_mode, target_tool=excluded.target_tool, "
            "target_args=excluded.target_args, owner_instance_id=excluded.owner_instance_id, "
            "session_id=excluded.session_id, enabled=excluded.enabled, "
            "created_at=excluded.created_at, updated_at=excluded.updated_at, "
            "claim_owner='', claim_until=0",
            cls._params(item),
        )

    def list_items(self) -> list[ScheduleItem]:
        with _LOCK, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM schedules ORDER BY at, created_at, id"
            ).fetchall()
            return [self._row_to_item(row) for row in rows]

    def save_items(self, items: list[ScheduleItem]) -> None:
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._replace_rows(db, items)
            db.commit()

    def _replace_rows(self, db: sqlite3.Connection, items: list[ScheduleItem]) -> None:
        db.execute("DELETE FROM schedules")
        for item in items:
            self._upsert(db, item)

    def add_item(self, item: ScheduleItem) -> ScheduleItem:
        normalized = item.normalized().touch()
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._upsert(db, normalized)
            db.commit()
        return normalized

    def delete_item(self, schedule_id: str) -> bool:
        schedule_id = str(schedule_id or "").strip()
        if not schedule_id:
            return False
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            db.commit()
            return result.rowcount > 0

    def get_item(self, schedule_id: str) -> Optional[ScheduleItem]:
        schedule_id = str(schedule_id or "").strip()
        if not schedule_id:
            return None
        with _LOCK, self._connect() as db:
            row = db.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
            return self._row_to_item(row) if row is not None else None

    def reclaim_expired_claims(self, now: datetime | None = None) -> int:
        """Clear leases left by a stopped scheduler process."""
        now_ts = (now or utc_now()).timestamp()
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE schedules SET claim_owner='', claim_until=0 "
                "WHERE claim_until > 0 AND claim_until <= ?",
                (now_ts,),
            )
            db.commit()
            return max(0, int(result.rowcount))

    def claim_due_items(
        self, instance_id: str, now: datetime, *, lease_seconds: float = 30.0
    ) -> list[tuple[ScheduleItem, str]]:
        owner = str(instance_id or "").strip()
        now_iso = format_iso_datetime(now)
        until = now.timestamp() + max(1.0, float(lease_seconds))
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT * FROM schedules WHERE enabled = 1 AND at <= ? "
                "AND (owner_instance_id = '' OR owner_instance_id = ?) "
                "AND (claim_until <= ? OR claim_owner = ?)",
                (now_iso, owner, now.timestamp(), owner),
            ).fetchall()
            claimed: list[tuple[ScheduleItem, str]] = []
            for row in rows:
                result = db.execute(
                    "UPDATE schedules SET claim_owner=?, claim_until=? "
                    "WHERE id=? AND (claim_until <= ? OR claim_owner=?)",
                    (owner, until, row["id"], now.timestamp(), owner),
                )
                if result.rowcount > 0:
                    claimed.append((self._row_to_item(row), row["at"]))
            db.commit()
            return claimed

    def finalize_claim(
        self, schedule_id: str, instance_id: str, next_at: str | None
    ) -> bool:
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if next_at is None:
                result = db.execute(
                    "DELETE FROM schedules WHERE id=? AND claim_owner=?",
                    (schedule_id, instance_id),
                )
            else:
                result = db.execute(
                    "UPDATE schedules SET at=?, updated_at=?, claim_owner='', claim_until=0 "
                    "WHERE id=? AND claim_owner=?",
                    (next_at, format_iso_datetime(utc_now()), schedule_id, instance_id),
                )
            db.commit()
            return result.rowcount > 0

    def finalize_claim_with_events(
        self,
        schedule_id: str,
        instance_id: str,
        next_at: str | None,
        events: list[dict[str, Any]],
    ) -> bool:
        """Finalize one schedule firing and persist its dispatch events atomically.

        ``delivered`` means acknowledged by the event consumer, not that the
        scheduled run has completed. Event keys are deterministic per run and
        event position so a replay cannot create duplicate outbox rows.
        """
        owner = str(instance_id or "").strip()
        normalized_events = [dict(event) for event in events]
        created_at = format_iso_datetime(utc_now())
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            claimed = db.execute(
                "SELECT 1 FROM schedules WHERE id=? AND claim_owner=?",
                (schedule_id, owner),
            ).fetchone()
            if claimed is None:
                db.rollback()
                return False

            for ordinal, payload in enumerate(normalized_events):
                run_id = str(payload.get("run_id") or "").strip()
                kind = str(payload.get("kind") or "").strip()
                if not run_id or not kind:
                    raise ValueError("scheduler event requires run_id and kind")
                event_key = f"{run_id}:{ordinal}:{kind}"
                target_instance_id = str(payload.get("owner_instance_id") or "").strip()
                db.execute(
                    "INSERT OR IGNORE INTO scheduler_events ("
                    "event_key,schedule_id,run_id,target_instance_id,payload,status,"
                    "attempt_count,available_at,claim_owner,claim_until,last_error,"
                    "created_at,delivered_at) VALUES (?,?,?,?,?,'pending',0,0,'',0,'',?,'')",
                    (
                        event_key,
                        schedule_id,
                        run_id,
                        target_instance_id,
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                        created_at,
                    ),
                )

            if next_at is None:
                result = db.execute(
                    "DELETE FROM schedules WHERE id=? AND claim_owner=?",
                    (schedule_id, owner),
                )
            else:
                result = db.execute(
                    "UPDATE schedules SET at=?, updated_at=?, claim_owner='', claim_until=0 "
                    "WHERE id=? AND claim_owner=?",
                    (next_at, created_at, schedule_id, owner),
                )
            if result.rowcount <= 0:
                db.rollback()
                return False
            db.commit()
            return True

    def claim_pending_events(
        self,
        instance_id: str,
        now: datetime | None = None,
        *,
        lease_seconds: float = 30.0,
        limit: int = 100,
    ) -> list[tuple[int, dict[str, Any]]]:
        """Claim pending outbox events for this scheduler instance."""
        owner = str(instance_id or "").strip()
        now_ts = (now or utc_now()).timestamp()
        until = now_ts + max(1.0, float(lease_seconds))
        batch_limit = max(1, int(limit or 100))
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT e.* FROM scheduler_events e WHERE e.status='pending' "
                "AND e.available_at <= ? "
                "AND (e.target_instance_id='' OR e.target_instance_id=?) "
                "AND e.claim_until <= ? "
                "AND NOT EXISTS (SELECT 1 FROM scheduler_events p "
                "WHERE p.run_id=e.run_id AND p.status='pending' AND p.id<e.id) "
                "ORDER BY e.id LIMIT ?",
                (now_ts, owner, now_ts, batch_limit),
            ).fetchall()
            claimed: list[tuple[int, dict[str, Any]]] = []
            for row in rows:
                result = db.execute(
                    "UPDATE scheduler_events SET claim_owner=?, claim_until=? "
                    "WHERE id=? AND status='pending' "
                    "AND (target_instance_id='' OR target_instance_id=?) "
                    "AND claim_until <= ?",
                    (owner, until, row["id"], owner, now_ts),
                )
                if result.rowcount <= 0:
                    continue
                try:
                    payload = json.loads(row["payload"] or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("payload is not an object")
                except Exception as exc:
                    db.execute(
                        "UPDATE scheduler_events SET status='invalid', claim_owner='', "
                        "claim_until=0, last_error=? WHERE id=? AND claim_owner=?",
                        (f"invalid payload: {exc}", row["id"], owner),
                    )
                    continue
                claimed.append((int(row["id"]), payload))
            db.commit()
            return claimed

    def mark_event_delivered(self, event_id: int, instance_id: str) -> bool:
        owner = str(instance_id or "").strip()
        delivered_at = format_iso_datetime(utc_now())
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE scheduler_events SET status='delivered', delivered_at=?, "
                "claim_owner='', claim_until=0, last_error='' "
                "WHERE id=? AND status='pending' AND claim_owner=?",
                (delivered_at, int(event_id), owner),
            )
            db.commit()
            return result.rowcount > 0

    def release_event(
        self,
        event_id: int,
        instance_id: str,
        *,
        error: str = "",
        retry_delay: float = 0.0,
    ) -> bool:
        owner = str(instance_id or "").strip()
        available_at = utc_now().timestamp() + max(0.0, float(retry_delay or 0.0))
        last_error = str(error or "")[:2000]
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE scheduler_events SET attempt_count=attempt_count+1, "
                "available_at=?, claim_owner='', claim_until=0, last_error=? "
                "WHERE id=? AND status='pending' AND claim_owner=?",
                (available_at, last_error, int(event_id), owner),
            )
            db.commit()
            return result.rowcount > 0

    def reclaim_orphaned_instance(
        self, previous_instance_id: str, new_instance_id: str
    ) -> dict[str, int]:
        """Explicitly reassign scheduler state after the old owner is known dead.

        This is intentionally not automatic. The caller must revalidate the
        persisted session/authentication boundary before moving schedules or
        pending events to a new process owner.
        """
        previous = str(previous_instance_id or "").strip()
        new = str(new_instance_id or "").strip()
        if not previous or not new or previous == new:
            return {"schedules": 0, "events": 0}
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            schedule_result = db.execute(
                "UPDATE schedules SET owner_instance_id=?, claim_owner='', "
                "claim_until=0 WHERE enabled=1 AND owner_instance_id=?",
                (new, previous),
            )
            event_rows = db.execute(
                "SELECT id,payload FROM scheduler_events "
                "WHERE status='pending' AND target_instance_id=? ORDER BY id",
                (previous,),
            ).fetchall()
            event_count = 0
            for row in event_rows:
                payload_text = row["payload"]
                try:
                    payload = json.loads(payload_text or "{}")
                    if isinstance(payload, dict):
                        payload["owner_instance_id"] = new
                        payload["reclaimed_from_instance_id"] = previous
                        payload_text = json.dumps(
                            payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                except Exception:
                    pass
                result = db.execute(
                    "UPDATE scheduler_events SET target_instance_id=?, payload=?, "
                    "claim_owner='', claim_until=0, available_at=0 "
                    "WHERE id=? AND status='pending' AND target_instance_id=?",
                    (new, payload_text, row["id"], previous),
                )
                if result.rowcount > 0:
                    event_count += 1
            db.commit()
            return {
                "schedules": max(0, int(schedule_result.rowcount)),
                "events": event_count,
            }

    def list_events(self, status: str = "") -> list[dict[str, Any]]:
        """Return scheduler outbox records for diagnostics and tests."""
        normalized_status = str(status or "").strip().lower()
        with _LOCK, self._connect() as db:
            if normalized_status:
                rows = db.execute(
                    "SELECT * FROM scheduler_events WHERE status=? ORDER BY id",
                    (normalized_status,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM scheduler_events ORDER BY id"
                ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload"] or "{}")
            except Exception:
                payload = {}
            events.append(
                {
                    "id": int(row["id"]),
                    "event_key": row["event_key"],
                    "schedule_id": row["schedule_id"],
                    "run_id": row["run_id"],
                    "target_instance_id": row["target_instance_id"],
                    "payload": payload,
                    "status": row["status"],
                    "attempt_count": int(row["attempt_count"]),
                    "available_at": float(row["available_at"]),
                    "claim_owner": row["claim_owner"],
                    "claim_until": float(row["claim_until"]),
                    "last_error": row["last_error"],
                    "created_at": row["created_at"],
                    "delivered_at": row["delivered_at"],
                }
            )
        return events

    def release_claim(
        self, schedule_id: str, instance_id: str, *, restore_at: str = ""
    ) -> bool:
        with _LOCK, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if restore_at:
                result = db.execute(
                    "UPDATE schedules SET at=?, claim_owner='', claim_until=0 WHERE id=? AND claim_owner=?",
                    (restore_at, schedule_id, instance_id),
                )
            else:
                result = db.execute(
                    "UPDATE schedules SET claim_owner='', claim_until=0 WHERE id=? AND claim_owner=?",
                    (schedule_id, instance_id),
                )
            db.commit()
            return result.rowcount > 0

    def set_items(self, items: list[ScheduleItem]) -> None:
        self.save_items(items)
