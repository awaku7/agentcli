"""Durable encrypted inbox and at-most-once dispatch state for NIP-17 requests.

Only the signed/encrypted outer kind-1059 gift wrap is persisted; decrypted DM
content is never stored here. A verified rumor is inserted before the transport
callback is notified. Pending rows can be enumerated after restart. Claiming a
row moves it permanently to ``dispatching``; a crash in that state is an
unknown outcome and must not be auto-retried, because arbitrary CLI commands
may already have produced side effects.

Pending rows, cumulative encrypted-payload bytes, and total deduplication
records are bounded; capacity exhaustion rejects new requests. The payload
budget is not refunded when a request finishes, preventing repeated insertions
and ciphertext clearing from growing SQLite files without bound. On migration
from the earlier schema, only still-retained ciphertext bytes can be counted;
bytes cleared before migration are unrecoverable, so the cumulative budget
starts from the migration baseline. Terminal tombstones are not automatically
pruned. This store is not yet connected to CLI startup/shutdown or a response
outbox.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

MAX_STORED_GIFT_WRAP_BYTES = 1_000_000
MAX_PENDING_INBOX_ROWS = 1_000
MAX_INBOX_RECORDS = 50_000
MAX_INBOX_TOTAL_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_INBOX_SESSION_ID_CHARS = 128
_HEX_32 = re.compile(r"^[0-9a-fA-F]{64}$")
_NIP01_EVENT_FIELDS = frozenset(
    ("id", "pubkey", "created_at", "kind", "tags", "content", "sig")
)
TerminalStatus = Literal["completed", "rejected", "failed"]


class InboxFullError(RuntimeError):
    """Raised when inbox capacity is reached; new requests fail closed."""


@dataclass(frozen=True)
class InboxRecord:
    """A durable NIP-17 request; ``wrapped_event`` is ciphertext, not plaintext."""

    sender_pubkey: str
    rumor_id: str
    created_at: int
    received_at: int
    session_id: str
    status: str
    wrapped_event: dict[str, Any] | None
    claimed_at: int | None
    finished_at: int | None


def _hex32(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_32.fullmatch(value):
        raise ValueError(f"{field} must be a 32-byte hexadecimal string")
    return value.lower()


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _normalize_session_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_INBOX_SESSION_ID_CHARS
        or "\x00" in value
        or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in value)
    ):
        raise ValueError("session_id is invalid")
    return value


def _serialize_wrapped_event(event: Any, max_bytes: int) -> tuple[str, int]:
    if not isinstance(event, dict) or event.get("kind") != 1059:
        raise ValueError("only NIP-17 kind-1059 gift wraps may be stored")
    if set(event) != _NIP01_EVENT_FIELDS:
        # Do not persist relay-added extension fields; only canonical signed
        # NIP-01 event fields belong in the encrypted inbox record.
        raise ValueError(
            "gift wrap must contain exactly the canonical NIP-01 event fields"
        )
    if not isinstance(event.get("content"), str) or not event["content"]:
        raise ValueError("gift-wrap content must be non-empty ciphertext")
    try:
        raw = json.dumps(
            event,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("gift wrap must be valid UTF-8 JSON") from exc
    if len(raw) > max_bytes:
        raise ValueError("gift wrap exceeds the inbox size limit")
    return raw.decode("utf-8"), len(raw)


def _record_from_row(row: tuple[Any, ...]) -> InboxRecord:
    event_json = row[6]
    if event_json is None:
        event = None
    else:
        try:
            event = json.loads(event_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("inbox contains corrupt wrapped-event JSON") from exc
        if not isinstance(event, dict) or event.get("kind") != 1059:
            raise RuntimeError("inbox contains an invalid wrapped event")
    return InboxRecord(
        sender_pubkey=row[0],
        rumor_id=row[1],
        created_at=row[2],
        received_at=row[3],
        session_id=row[4],
        status=row[5],
        wrapped_event=event,
        claimed_at=row[7],
        finished_at=row[8],
    )


class SQLiteNostrInboxStore:
    """Atomic persistence for verified encrypted kind-1059 inbox requests.

    The caller must verify the gift-wrap signature, decrypt and validate the
    inner rumor, recheck pairing authorization, and enforce the inner rumor's
    freshness before calling ``enqueue_verified_wrap``. This store adds durable
    sender/rumor deduplication, pending/count limits, and a bound on cumulative
    encrypted payload bytes. The payload budget is never refunded; the store
    fails closed instead of pruning replay tombstones. When upgrading from the
    earlier schema, the budget is initialized from ciphertext still retained;
    payloads already cleared in terminal rows cannot be reconstructed.
    """

    _SELECT_COLUMNS = (
        "sender_pubkey, rumor_id, created_at, received_at, session_id, status, "
        "wrapped_event_json, claimed_at, finished_at"
    )

    def __init__(
        self,
        path: str | Path,
        *,
        max_pending: int = MAX_PENDING_INBOX_ROWS,
        max_records: int = MAX_INBOX_RECORDS,
        max_total_payload_bytes: int = MAX_INBOX_TOTAL_PAYLOAD_BYTES,
        max_wrap_bytes: int = MAX_STORED_GIFT_WRAP_BYTES,
    ) -> None:
        if (
            not isinstance(max_pending, int)
            or isinstance(max_pending, bool)
            or max_pending < 1
        ):
            raise ValueError("max_pending must be a positive integer")
        if (
            not isinstance(max_records, int)
            or isinstance(max_records, bool)
            or max_records < 1
        ):
            raise ValueError("max_records must be a positive integer")
        if (
            not isinstance(max_total_payload_bytes, int)
            or isinstance(max_total_payload_bytes, bool)
            or max_total_payload_bytes < 1
        ):
            raise ValueError("max_total_payload_bytes must be a positive integer")
        if (
            not isinstance(max_wrap_bytes, int)
            or isinstance(max_wrap_bytes, bool)
            or not 1 <= max_wrap_bytes <= MAX_STORED_GIFT_WRAP_BYTES
        ):
            raise ValueError(
                f"max_wrap_bytes must be between 1 and {MAX_STORED_GIFT_WRAP_BYTES}"
            )
        self.path = str(path)
        self.max_pending = max_pending
        self.max_records = max_records
        self.max_total_payload_bytes = max_total_payload_bytes
        self.max_wrap_bytes = max_wrap_bytes
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA busy_timeout = 10000")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute("""
            CREATE TABLE IF NOT EXISTS nostr_remote_inbox (
                sender_pubkey TEXT NOT NULL,
                rumor_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                received_at INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'dispatching', 'completed', 'rejected', 'failed')
                ),
                wrapped_event_json TEXT,
                wrapped_event_bytes INTEGER NOT NULL DEFAULT 0,
                claimed_at INTEGER,
                finished_at INTEGER,
                PRIMARY KEY (sender_pubkey, rumor_id)
            )
            """)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            columns = {
                row[1]
                for row in self._connection.execute(
                    "PRAGMA table_info(nostr_remote_inbox)"
                ).fetchall()
            }
            if "wrapped_event_bytes" not in columns:
                self._connection.execute(
                    "ALTER TABLE nostr_remote_inbox ADD COLUMN "
                    "wrapped_event_bytes INTEGER NOT NULL DEFAULT 0"
                )
                self._connection.execute(
                    "UPDATE nostr_remote_inbox SET wrapped_event_bytes = "
                    "length(CAST(wrapped_event_json AS BLOB)) "
                    "WHERE wrapped_event_json IS NOT NULL"
                )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS nostr_remote_inbox_status_time "
                "ON nostr_remote_inbox (status, received_at)"
            )
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS nostr_remote_inbox_meta (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
                """)
            self._connection.execute(
                "INSERT OR IGNORE INTO nostr_remote_inbox_meta (key, value) "
                "SELECT 'total_payload_bytes', COALESCE(SUM(wrapped_event_bytes), 0) "
                "FROM nostr_remote_inbox"
            )
            self._connection.execute("COMMIT")
        except Exception:
            if self._connection.in_transaction:
                self._connection.execute("ROLLBACK")
            self._connection.close()
            raise

    def enqueue_verified_wrap(
        self,
        sender_pubkey_hex: str,
        rumor_id_hex: str,
        wrapped_event: dict[str, Any],
        *,
        created_at: int,
        received_at: int | None = None,
        session_id: str,
    ) -> bool:
        """Persist a verified encrypted wrap before waking the in-memory consumer.

        Returns False for a sender/rumor already present in any state. The
        encrypted outer event is retained only while pending/dispatching and is
        cleared after a terminal result; deduplication tombstones remain so an
        old message cannot be replayed by redelivery.
        """
        sender = _hex32(sender_pubkey_hex, "sender_pubkey_hex")
        rumor_id = _hex32(rumor_id_hex, "rumor_id_hex")
        created_at = _nonnegative_int(created_at, "created_at")
        if received_at is None:
            received_at = int(time.time())
        received_at = _nonnegative_int(received_at, "received_at")
        session_id = _normalize_session_id(session_id)
        event_json, event_size = _serialize_wrapped_event(
            wrapped_event, self.max_wrap_bytes
        )

        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._connection.execute(
                    "SELECT 1 FROM nostr_remote_inbox "
                    "WHERE sender_pubkey = ? AND rumor_id = ?",
                    (sender, rumor_id),
                ).fetchone()
                if existing is not None:
                    self._connection.execute("COMMIT")
                    return False
                pending = self._connection.execute(
                    "SELECT COUNT(*) FROM nostr_remote_inbox WHERE status = 'pending'"
                ).fetchone()[0]
                if pending >= self.max_pending:
                    raise InboxFullError("Nostr remote inbox pending capacity is full")
                total_records = self._connection.execute(
                    "SELECT COUNT(*) FROM nostr_remote_inbox"
                ).fetchone()[0]
                if total_records >= self.max_records:
                    raise InboxFullError(
                        "Nostr remote inbox deduplication capacity is full"
                    )
                total_payload_bytes = self._connection.execute(
                    "SELECT value FROM nostr_remote_inbox_meta "
                    "WHERE key = 'total_payload_bytes'"
                ).fetchone()[0]
                if total_payload_bytes + event_size > self.max_total_payload_bytes:
                    raise InboxFullError(
                        "Nostr remote inbox cumulative encrypted-byte capacity is full"
                    )
                self._connection.execute(
                    """
                    INSERT INTO nostr_remote_inbox (
                        sender_pubkey, rumor_id, created_at, received_at, session_id,
                        status, wrapped_event_json, wrapped_event_bytes, claimed_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, NULL, NULL)
                    """,
                    (
                        sender,
                        rumor_id,
                        created_at,
                        received_at,
                        session_id,
                        event_json,
                        event_size,
                    ),
                )
                self._connection.execute(
                    "UPDATE nostr_remote_inbox_meta SET value = value + ? "
                    "WHERE key = 'total_payload_bytes'",
                    (event_size,),
                )
                self._connection.execute("COMMIT")
                return True
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def _list(self, status: str, limit: int) -> list[InboxRecord]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            rows = self._connection.execute(
                f"SELECT {self._SELECT_COLUMNS} FROM nostr_remote_inbox "
                "WHERE status = ? ORDER BY received_at, sender_pubkey, rumor_id "
                "LIMIT ?",
                (status, limit),
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def list_pending(self, *, limit: int = 100) -> list[InboxRecord]:
        """Return pending requests in stable receive order for restart recovery."""
        return self._list("pending", limit)

    def list_dispatching(self, *, limit: int = 100) -> list[InboxRecord]:
        """List requests with an uncertain outcome; these must not auto-replay."""
        return self._list("dispatching", limit)

    def get(self, sender_pubkey_hex: str, rumor_id_hex: str) -> InboxRecord | None:
        sender = _hex32(sender_pubkey_hex, "sender_pubkey_hex")
        rumor_id = _hex32(rumor_id_hex, "rumor_id_hex")
        with self._lock:
            row = self._connection.execute(
                f"SELECT {self._SELECT_COLUMNS} FROM nostr_remote_inbox "
                "WHERE sender_pubkey = ? AND rumor_id = ?",
                (sender, rumor_id),
            ).fetchone()
        return None if row is None else _record_from_row(row)

    def claim(
        self,
        sender_pubkey_hex: str,
        rumor_id_hex: str,
        *,
        claimed_at: int | None = None,
    ) -> InboxRecord | None:
        """Atomically claim one pending request for at-most-once dispatch.

        A claimed request remains ``dispatching`` after process restart. It is
        exposed through ``list_dispatching`` for manual reconciliation and is
        never reset to pending automatically, since its CLI side effects may
        already have happened before a crash.
        """
        sender = _hex32(sender_pubkey_hex, "sender_pubkey_hex")
        rumor_id = _hex32(rumor_id_hex, "rumor_id_hex")
        claimed_at = _nonnegative_int(
            int(time.time()) if claimed_at is None else claimed_at, "claimed_at"
        )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._connection.execute(
                    "UPDATE nostr_remote_inbox SET status = 'dispatching', claimed_at = ? "
                    "WHERE sender_pubkey = ? AND rumor_id = ? AND status = 'pending'",
                    (claimed_at, sender, rumor_id),
                )
                if cursor.rowcount != 1:
                    self._connection.execute("COMMIT")
                    return None
                row = self._connection.execute(
                    f"SELECT {self._SELECT_COLUMNS} FROM nostr_remote_inbox "
                    "WHERE sender_pubkey = ? AND rumor_id = ?",
                    (sender, rumor_id),
                ).fetchone()
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return _record_from_row(row)

    def finish(
        self,
        sender_pubkey_hex: str,
        rumor_id_hex: str,
        outcome: TerminalStatus,
        *,
        finished_at: int | None = None,
    ) -> bool:
        """Record a terminal dispatch result and erase the encrypted event body."""
        if outcome not in ("completed", "rejected", "failed"):
            raise ValueError("outcome must be completed, rejected, or failed")
        sender = _hex32(sender_pubkey_hex, "sender_pubkey_hex")
        rumor_id = _hex32(rumor_id_hex, "rumor_id_hex")
        if finished_at is None:
            finished_at = int(time.time())
        finished_at = _nonnegative_int(finished_at, "finished_at")
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE nostr_remote_inbox SET status = ?, finished_at = ?, "
                "wrapped_event_json = NULL, wrapped_event_bytes = 0 "
                "WHERE sender_pubkey = ? AND rumor_id = ? AND status = 'dispatching'",
                (outcome, finished_at, sender, rumor_id),
            )
            return cursor.rowcount == 1

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteNostrInboxStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
