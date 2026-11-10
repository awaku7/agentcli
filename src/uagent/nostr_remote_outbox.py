"""Durable ciphertext-only outbox for NIP-17 remote CLI replies."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .nostr_nip17 import _validate_relay_uri

MAX_OUTBOX_PENDING = 500
MAX_OUTBOX_RECORDS = 10_000
MAX_OUTBOX_PAYLOAD_BYTES = 512 * 1024
MAX_OUTBOX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_OUTBOX_ATTEMPTS = 8
MAX_OUTBOX_AGE_SECONDS = 24 * 60 * 60
OUTBOX_RETRY_BASE_SECONDS = 5
OUTBOX_RETRY_MAX_SECONDS = 5 * 60
OUTBOX_SENDING_LEASE_SECONDS = 120
_OUTBOX_TOMBSTONE_AGE_SECONDS = 30 * 24 * 60 * 60
_HEX_32 = re.compile(r"^[0-9a-fA-F]{64}$")

OutboxStatus = Literal["pending", "sending", "delivered", "failed"]


class OutboxFullError(RuntimeError):
    """The bounded reply outbox cannot safely accept another encrypted reply."""


@dataclass(frozen=True)
class OutboxRecord:
    sender_pubkey: str
    request_rumor_id: str
    events: list[dict[str, Any]] | None
    relay_lists_by_pubkey: dict[str, list[str]] | None
    event_ids: tuple[str, ...]
    status: OutboxStatus
    attempts: int
    created_at: int
    next_attempt_at: int
    error_type: str


def _hex32(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_32.fullmatch(value):
        raise ValueError(f"{field} must be 32-byte hex")
    return value.lower()


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _normalize_payload(
    events: Sequence[dict[str, Any]],
    relay_lists_by_pubkey: Mapping[str, Sequence[str]],
    *,
    allow_missing_routes: bool = False,
) -> tuple[str, tuple[str, ...]]:
    if (
        isinstance(events, (str, bytes))
        or not isinstance(events, Sequence)
        or not events
    ):
        raise ValueError("outbox events must be a non-empty sequence")
    if len(events) > 10:
        raise ValueError("too many events in one outbox record")
    if not isinstance(relay_lists_by_pubkey, Mapping) or not relay_lists_by_pubkey:
        raise ValueError("outbox relay routes must be a non-empty mapping")

    normalized_events: list[dict[str, Any]] = []
    event_ids: list[str] = []
    recipients: set[str] = set()
    for event in events:
        if not isinstance(event, dict) or event.get("kind") != 1059:
            raise ValueError("outbox accepts only NIP-17 kind-1059 gift wraps")
        event_id = _hex32(event.get("id"), "event id")
        if not isinstance(event.get("content"), str):
            raise ValueError("gift-wrap content must be text")
        tags = event.get("tags")
        p_tags = [
            tag
            for tag in tags or []
            if isinstance(tag, list) and len(tag) >= 2 and tag[0] == "p"
        ]
        if len(p_tags) != 1:
            raise ValueError("gift wrap must have exactly one recipient p tag")
        recipients.add(_hex32(p_tags[0][1], "gift-wrap recipient"))
        normalized_events.append(event)
        event_ids.append(event_id)

    normalized_routes: dict[str, list[str]] = {}
    for pubkey, urls in relay_lists_by_pubkey.items():
        normalized_pubkey = _hex32(pubkey, "relay-list pubkey")
        if isinstance(urls, (str, bytes)) or not isinstance(urls, Sequence):
            raise ValueError("relay routes must be a sequence of URLs")
        normalized_urls = list(dict.fromkeys(_validate_relay_uri(url) for url in urls))
        if not normalized_urls or len(normalized_urls) > 10:
            raise ValueError("each outbox recipient needs one to ten relay URLs")
        normalized_routes[normalized_pubkey] = normalized_urls

    if any(pubkey not in recipients for pubkey in normalized_routes):
        raise ValueError("outbox relay routes must match gift-wrap recipients")
    if not allow_missing_routes and any(
        recipient not in normalized_routes for recipient in recipients
    ):
        raise ValueError("each gift-wrap recipient must have an outbox relay route")

    payload = json.dumps(
        {"events": normalized_events, "relay_lists_by_pubkey": normalized_routes},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    encoded_size = len(payload.encode("utf-8"))
    if encoded_size > MAX_OUTBOX_PAYLOAD_BYTES:
        raise OutboxFullError("encrypted reply exceeds the outbox record size limit")
    return payload, tuple(event_ids)


def _record_from_row(row: tuple[Any, ...]) -> OutboxRecord:
    (
        sender,
        request_id,
        status,
        payload_json,
        event_ids_json,
        attempts,
        created_at,
        next_attempt_at,
        error_type,
    ) = row
    events: list[dict[str, Any]] | None = None
    routes: dict[str, list[str]] | None = None
    if payload_json is not None:
        payload = json.loads(payload_json)
        events = payload.get("events")
        routes = payload.get("relay_lists_by_pubkey")
        if not isinstance(events, list) or not isinstance(routes, dict):
            raise ValueError("outbox payload has an invalid shape")
    event_ids = json.loads(event_ids_json)
    if not isinstance(event_ids, list) or any(
        not isinstance(item, str) for item in event_ids
    ):
        raise ValueError("outbox event-id list has an invalid shape")
    return OutboxRecord(
        sender_pubkey=sender,
        request_rumor_id=request_id,
        events=events,
        relay_lists_by_pubkey=routes,
        event_ids=tuple(event_ids),
        status=status,
        attempts=attempts,
        created_at=created_at,
        next_attempt_at=next_attempt_at,
        error_type=error_type or "",
    )


class SQLiteNostrOutboxStore:
    """Bounded SQLite outbox storing only encrypted signed gift-wrap events."""

    _SELECT_COLUMNS = (
        "sender_pubkey, request_rumor_id, status, payload_json, event_ids_json, "
        "attempts, created_at, next_attempt_at, error_type"
    )

    def __init__(
        self,
        path: str | Path,
        *,
        max_pending: int = MAX_OUTBOX_PENDING,
        max_records: int = MAX_OUTBOX_RECORDS,
        max_record_bytes: int = MAX_OUTBOX_PAYLOAD_BYTES,
        max_total_bytes: int = MAX_OUTBOX_TOTAL_BYTES,
        max_attempts: int = MAX_OUTBOX_ATTEMPTS,
        max_age_seconds: int = MAX_OUTBOX_AGE_SECONDS,
        sending_lease_seconds: int = OUTBOX_SENDING_LEASE_SECONDS,
    ) -> None:
        for name, value in (
            ("max_pending", max_pending),
            ("max_records", max_records),
            ("max_record_bytes", max_record_bytes),
            ("max_total_bytes", max_total_bytes),
            ("max_attempts", max_attempts),
            ("max_age_seconds", max_age_seconds),
            ("sending_lease_seconds", sending_lease_seconds),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.path = str(path)
        self.max_pending = max_pending
        self.max_records = max_records
        self.max_record_bytes = min(max_record_bytes, MAX_OUTBOX_PAYLOAD_BYTES)
        self.max_total_bytes = max_total_bytes
        self.max_attempts = max_attempts
        self.max_age_seconds = max_age_seconds
        self.sending_lease_seconds = sending_lease_seconds
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
            CREATE TABLE IF NOT EXISTS nostr_remote_outbox (
                sender_pubkey TEXT NOT NULL,
                request_rumor_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'sending', 'delivered', 'failed')
                ),
                payload_json TEXT,
                payload_bytes INTEGER NOT NULL DEFAULT 0,
                event_ids_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                next_attempt_at INTEGER NOT NULL,
                lease_until INTEGER,
                error_type TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (sender_pubkey, request_rumor_id)
            )
            """)
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS nostr_remote_outbox_due "
            "ON nostr_remote_outbox (status, next_attempt_at, created_at)"
        )

    def _get_locked(self, sender: str, request_id: str) -> OutboxRecord | None:
        row = self._connection.execute(
            f"SELECT {self._SELECT_COLUMNS} FROM nostr_remote_outbox "
            "WHERE sender_pubkey = ? AND request_rumor_id = ?",
            (sender, request_id),
        ).fetchone()
        return None if row is None else _record_from_row(row)

    def get(self, sender_pubkey: str, request_rumor_id: str) -> OutboxRecord | None:
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        with self._lock:
            return self._get_locked(sender, request_id)

    def enqueue(
        self,
        sender_pubkey: str,
        request_rumor_id: str,
        events: Sequence[dict[str, Any]],
        relay_lists_by_pubkey: Mapping[str, Sequence[str]],
        *,
        created_at: int | None = None,
        allow_missing_routes: bool = False,
    ) -> OutboxRecord:
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        payload_json, event_ids = _normalize_payload(
            events,
            relay_lists_by_pubkey,
            allow_missing_routes=allow_missing_routes,
        )
        payload_bytes = len(payload_json.encode("utf-8"))
        if payload_bytes > self.max_record_bytes:
            raise OutboxFullError(
                "encrypted reply exceeds the outbox record size limit"
            )
        created_at = int(time.time()) if created_at is None else created_at
        created_at = _nonnegative_int(created_at, "created_at")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self._get_locked(sender, request_id)
                if existing is not None:
                    self._connection.execute("COMMIT")
                    return existing
                self._connection.execute(
                    "DELETE FROM nostr_remote_outbox WHERE status IN ('delivered', 'failed') "
                    "AND created_at < ?",
                    (created_at - _OUTBOX_TOMBSTONE_AGE_SECONDS,),
                )
                total_records, pending, total_bytes = self._connection.execute(
                    "SELECT COUNT(*), "
                    "COALESCE(SUM(CASE WHEN status IN ('pending', 'sending') THEN 1 ELSE 0 END), 0), "
                    "COALESCE(SUM(payload_bytes), 0) "
                    "FROM nostr_remote_outbox"
                ).fetchone()
                if total_records >= self.max_records or pending >= self.max_pending:
                    raise OutboxFullError("Nostr reply outbox is at capacity")
                if total_bytes + payload_bytes > self.max_total_bytes:
                    raise OutboxFullError(
                        "Nostr reply outbox payload budget is exhausted"
                    )
                self._connection.execute(
                    "INSERT INTO nostr_remote_outbox "
                    "(sender_pubkey, request_rumor_id, status, payload_json, payload_bytes, "
                    "event_ids_json, attempts, created_at, next_attempt_at) "
                    "VALUES (?, ?, 'pending', ?, ?, ?, 0, ?, ?)",
                    (
                        sender,
                        request_id,
                        payload_json,
                        payload_bytes,
                        json.dumps(event_ids, separators=(",", ":")),
                        created_at,
                        created_at,
                    ),
                )
                record = self._get_locked(sender, request_id)
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        if record is None:
            raise RuntimeError("outbox insert did not create a record")
        return record

    def update_routes(
        self,
        sender_pubkey: str,
        request_rumor_id: str,
        relay_lists_by_pubkey: Mapping[str, Sequence[str]],
    ) -> bool:
        """Persist verified relay routes while a reply is still deliverable."""
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT status, payload_json, payload_bytes "
                    "FROM nostr_remote_outbox WHERE sender_pubkey = ? "
                    "AND request_rumor_id = ?",
                    (sender, request_id),
                ).fetchone()
                if (
                    row is None
                    or row[0] not in {"pending", "sending"}
                    or row[1] is None
                ):
                    self._connection.execute("COMMIT")
                    return False
                payload = json.loads(row[1])
                events = payload.get("events") if isinstance(payload, dict) else None
                if not isinstance(events, list):
                    raise ValueError("outbox payload has an invalid shape")
                payload_json, _event_ids = _normalize_payload(
                    events, relay_lists_by_pubkey
                )
                payload_bytes = len(payload_json.encode("utf-8"))
                if payload_bytes > self.max_record_bytes:
                    raise OutboxFullError(
                        "encrypted reply exceeds the outbox record size limit"
                    )
                total_bytes = self._connection.execute(
                    "SELECT COALESCE(SUM(payload_bytes), 0) " "FROM nostr_remote_outbox"
                ).fetchone()[0]
                if total_bytes - row[2] + payload_bytes > self.max_total_bytes:
                    raise OutboxFullError(
                        "Nostr reply outbox payload budget is exhausted"
                    )
                self._connection.execute(
                    "UPDATE nostr_remote_outbox SET payload_json = ?, payload_bytes = ? "
                    "WHERE sender_pubkey = ? AND request_rumor_id = ? "
                    "AND status IN ('pending', 'sending')",
                    (payload_json, payload_bytes, sender, request_id),
                )
                self._connection.execute("COMMIT")
                return True
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def _claim_locked(
        self, sender: str, request_id: str, now: int
    ) -> OutboxRecord | None:
        self._connection.execute(
            "UPDATE nostr_remote_outbox SET status = 'failed', payload_json = NULL, "
            "payload_bytes = 0, lease_until = NULL, error_type = 'Expired' "
            "WHERE sender_pubkey = ? AND request_rumor_id = ? "
            "AND status = 'pending' AND created_at < ?",
            (sender, request_id, now - self.max_age_seconds),
        )
        self._connection.execute(
            "UPDATE nostr_remote_outbox SET status = 'pending', lease_until = NULL, "
            "next_attempt_at = MIN(next_attempt_at, ?) "
            "WHERE sender_pubkey = ? AND request_rumor_id = ? "
            "AND status = 'sending' AND lease_until <= ?",
            (now, sender, request_id, now),
        )
        cursor = self._connection.execute(
            "UPDATE nostr_remote_outbox SET status = 'sending', attempts = attempts + 1, "
            "lease_until = ? WHERE sender_pubkey = ? AND request_rumor_id = ? "
            "AND status = 'pending' AND next_attempt_at <= ? "
            "AND attempts < ? AND created_at >= ?",
            (
                now + self.sending_lease_seconds,
                sender,
                request_id,
                now,
                self.max_attempts,
                now - self.max_age_seconds,
            ),
        )
        if cursor.rowcount != 1:
            self._connection.execute(
                "UPDATE nostr_remote_outbox SET status = 'failed', payload_json = NULL, "
                "payload_bytes = 0, lease_until = NULL, error_type = 'RetryLimit' "
                "WHERE sender_pubkey = ? AND request_rumor_id = ? "
                "AND status = 'pending' AND attempts >= ?",
                (sender, request_id, self.max_attempts),
            )
            return None
        return self._get_locked(sender, request_id)

    def claim(
        self,
        sender_pubkey: str,
        request_rumor_id: str,
        *,
        now: int | None = None,
    ) -> OutboxRecord | None:
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        now = int(time.time()) if now is None else _nonnegative_int(now, "now")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                record = self._claim_locked(sender, request_id, now)
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return record

    def claim_next_due(self, *, now: int | None = None) -> OutboxRecord | None:
        now = int(time.time()) if now is None else _nonnegative_int(now, "now")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.execute(
                    "UPDATE nostr_remote_outbox SET status = 'pending', lease_until = NULL, "
                    "next_attempt_at = MIN(next_attempt_at, ?) "
                    "WHERE status = 'sending' AND lease_until <= ?",
                    (now, now),
                )
                self._connection.execute(
                    "UPDATE nostr_remote_outbox SET status = 'failed', payload_json = NULL, "
                    "payload_bytes = 0, lease_until = NULL, error_type = 'Expired' "
                    "WHERE status = 'pending' AND created_at < ?",
                    (now - self.max_age_seconds,),
                )
                row = self._connection.execute(
                    "SELECT sender_pubkey, request_rumor_id FROM nostr_remote_outbox "
                    "WHERE status = 'pending' AND next_attempt_at <= ? "
                    "AND attempts < ? ORDER BY next_attempt_at, created_at LIMIT 1",
                    (now, self.max_attempts),
                ).fetchone()
                if row is None:
                    self._connection.execute(
                        "UPDATE nostr_remote_outbox SET status = 'failed', payload_json = NULL, "
                        "payload_bytes = 0, lease_until = NULL, error_type = 'RetryLimit' "
                        "WHERE status = 'pending' AND attempts >= ?",
                        (self.max_attempts,),
                    )
                    self._connection.execute("COMMIT")
                    return None
                record = self._claim_locked(row[0], row[1], now)
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return record

    def mark_delivered(
        self,
        sender_pubkey: str,
        request_rumor_id: str,
        *,
        event_ids: Sequence[str] | None = None,
    ) -> bool:
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        with self._lock:
            if event_ids is None:
                cursor = self._connection.execute(
                    "UPDATE nostr_remote_outbox SET status = 'delivered', payload_json = NULL, "
                    "payload_bytes = 0, lease_until = NULL, error_type = '' "
                    "WHERE sender_pubkey = ? AND request_rumor_id = ? AND status = 'sending'",
                    (sender, request_id),
                )
            else:
                normalized_ids = [
                    _hex32(event_id, "event_id") for event_id in event_ids
                ]
                cursor = self._connection.execute(
                    "UPDATE nostr_remote_outbox SET status = 'delivered', payload_json = NULL, "
                    "payload_bytes = 0, lease_until = NULL, event_ids_json = ?, error_type = '' "
                    "WHERE sender_pubkey = ? AND request_rumor_id = ? AND status = 'sending'",
                    (
                        json.dumps(normalized_ids, separators=(",", ":")),
                        sender,
                        request_id,
                    ),
                )
            return cursor.rowcount == 1

    def retry_or_fail(
        self,
        sender_pubkey: str,
        request_rumor_id: str,
        error_type: str,
        *,
        now: int | None = None,
    ) -> OutboxRecord | None:
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        now = int(time.time()) if now is None else _nonnegative_int(now, "now")
        safe_error_type = (
            "".join(ch for ch in error_type if ch.isalnum() or ch in "_.-")[:64]
            if isinstance(error_type, str)
            else "Error"
        ) or "Error"
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    f"SELECT {self._SELECT_COLUMNS} FROM nostr_remote_outbox "
                    "WHERE sender_pubkey = ? AND request_rumor_id = ? AND status = 'sending'",
                    (sender, request_id),
                ).fetchone()
                if row is None:
                    self._connection.execute("COMMIT")
                    return self._get_locked(sender, request_id)
                attempts = row[5]
                created_at = row[6]
                if (
                    attempts >= self.max_attempts
                    or created_at < now - self.max_age_seconds
                ):
                    self._connection.execute(
                        "UPDATE nostr_remote_outbox SET status = 'failed', payload_json = NULL, "
                        "payload_bytes = 0, lease_until = NULL, error_type = ? "
                        "WHERE sender_pubkey = ? AND request_rumor_id = ? AND status = 'sending'",
                        (safe_error_type, sender, request_id),
                    )
                else:
                    delay = min(
                        OUTBOX_RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)),
                        OUTBOX_RETRY_MAX_SECONDS,
                    )
                    self._connection.execute(
                        "UPDATE nostr_remote_outbox SET status = 'pending', lease_until = NULL, "
                        "next_attempt_at = ?, error_type = ? "
                        "WHERE sender_pubkey = ? AND request_rumor_id = ? AND status = 'sending'",
                        (now + delay, safe_error_type, sender, request_id),
                    )
                record = self._get_locked(sender, request_id)
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return record

    def fail(self, sender_pubkey: str, request_rumor_id: str, error_type: str) -> bool:
        sender = _hex32(sender_pubkey, "sender_pubkey")
        request_id = _hex32(request_rumor_id, "request_rumor_id")
        safe_error_type = (
            "".join(ch for ch in error_type if ch.isalnum() or ch in "_.-")[:64]
            if isinstance(error_type, str)
            else "Error"
        ) or "Error"
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE nostr_remote_outbox SET status = 'failed', payload_json = NULL, "
                "payload_bytes = 0, lease_until = NULL, error_type = ? "
                "WHERE sender_pubkey = ? AND request_rumor_id = ? "
                "AND status IN ('pending', 'sending')",
                (safe_error_type, sender, request_id),
            )
            return cursor.rowcount == 1

    def pending_count(self) -> int:
        with self._lock:
            return int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM nostr_remote_outbox "
                    "WHERE status IN ('pending', 'sending')"
                ).fetchone()[0]
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteNostrOutboxStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
