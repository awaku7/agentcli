"""Durable replay and rumor-time guards for the experimental Nostr remote path.

This module stores only sender pubkeys, rumor IDs, and receipt timestamps. It is
not yet wired into the CLI dispatcher; callers must claim an event atomically
before enqueueing any remote action. Never use the randomized outer gift-wrap
or seal timestamp for message freshness checks.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


def _require_hex32(value: str, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 32-byte hexadecimal string")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be hexadecimal") from exc
    if len(raw) != 32:
        raise ValueError(f"{name} must be a 32-byte hexadecimal string")
    return raw.hex()


def validate_rumor_timestamp(
    created_at: int,
    *,
    now: int | None = None,
    max_age_seconds: int = 600,
    future_tolerance_seconds: int = 300,
) -> None:
    """Reject stale/future NIP-17 rumor timestamps using the canonical inner time."""
    if (
        not isinstance(created_at, int)
        or isinstance(created_at, bool)
        or created_at < 0
    ):
        raise ValueError("rumor created_at must be a non-negative integer")
    if now is None:
        now = int(time.time())
    if not isinstance(now, int) or isinstance(now, bool) or now < 0:
        raise ValueError("now must be a non-negative integer")
    if max_age_seconds < 0 or future_tolerance_seconds < 0:
        raise ValueError("timestamp tolerances must be non-negative")
    if created_at < now - max_age_seconds:
        raise ValueError("remote rumor is too old")
    if created_at > now + future_tolerance_seconds:
        raise ValueError("remote rumor is too far in the future")


class SQLiteReplayStore:
    """SQLite-backed atomic deduplication for authenticated Nostr rumors."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
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
            CREATE TABLE IF NOT EXISTS nostr_remote_seen (
                sender_pubkey TEXT NOT NULL,
                rumor_id TEXT NOT NULL,
                first_received_at INTEGER NOT NULL,
                PRIMARY KEY (sender_pubkey, rumor_id)
            )
            """)

    def claim(
        self,
        sender_pubkey_hex: str,
        rumor_id_hex: str,
        *,
        received_at: int | None = None,
    ) -> bool:
        """Atomically record a sender/rumor pair; return False if already seen.

        The caller must perform signature, decryption, pairing authorization,
        and rumor-time validation before claiming. Claim before queueing so
        concurrent relays/processes cannot enqueue the same command twice.
        """
        sender = _require_hex32(sender_pubkey_hex, "sender_pubkey_hex")
        rumor_id = _require_hex32(rumor_id_hex, "rumor_id_hex")
        if received_at is None:
            received_at = int(time.time())
        if (
            not isinstance(received_at, int)
            or isinstance(received_at, bool)
            or received_at < 0
        ):
            raise ValueError("received_at must be a non-negative integer")

        with self._lock:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO nostr_remote_seen "
                "(sender_pubkey, rumor_id, first_received_at) VALUES (?, ?, ?)",
                (sender, rumor_id, received_at),
            )
            return cursor.rowcount == 1

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteReplayStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
