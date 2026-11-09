"""Persistent public-key pairing registry for the experimental Nostr remote path.

The registry stores public keys and locally chosen labels only; it never stores
Nostr private keys or decrypted DM text. ``approved=True`` is a guard for the
caller, not proof of consent: pair() must only be called after a local operator
has explicitly reviewed and approved the device. This store is not yet wired to
CLI commands or to a running Relay listener.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MAX_LABEL_BYTES = 128
_HEX_32 = re.compile(r"^[0-9a-fA-F]{64}$")


def _normalize_pubkey(value: Any) -> str:
    if not isinstance(value, str) or not _HEX_32.fullmatch(value):
        raise ValueError("pubkey must be a 32-byte hexadecimal x-only key")
    normalized = value.lower()
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as exc:
        raise ModuleNotFoundError(
            "validating Nostr pairing keys requires the 'cryptography' package"
        ) from exc
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), b"\x02" + bytes.fromhex(normalized)
        )
    except ValueError as exc:
        raise ValueError("pubkey is not a valid secp256k1 x-only key") from exc
    return normalized


def _timestamp(value: int | None, name: str) -> int:
    if value is None:
        value = int(time.time())
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _validate_label(label: str) -> str:
    if not isinstance(label, str):
        raise TypeError("device label must be a string")
    if "\x00" in label:
        raise ValueError("device label must not contain NUL")
    if any(unicodedata.category(char) == "Cc" for char in label):
        raise ValueError("device label must not contain control characters")
    try:
        encoded_len = len(label.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("device label must be valid UTF-8") from exc
    if encoded_len > _MAX_LABEL_BYTES:
        raise ValueError("device label exceeds the size limit")
    return label


@dataclass(frozen=True)
class PairingRecord:
    """A locally approved device record; ``revoked_at`` is set after revocation."""

    pubkey: str
    label: str
    paired_at: int
    revoked_at: int | None

    @property
    def active(self) -> bool:
        return self.revoked_at is None


class SQLitePairingStore:
    """SQLite persistence for explicit device pairing and immediate revocation.

    ``is_authorized`` is suitable as the foreground dispatcher's synchronous
    authorization callback. Call it for every command, rather than caching the
    result, so a revoked key's already-queued request is rejected.
    """

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
            CREATE TABLE IF NOT EXISTS nostr_remote_pairings (
                pubkey TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                paired_at INTEGER NOT NULL,
                revoked_at INTEGER
            )
            """)

    def pair(
        self,
        pubkey: str,
        label: str = "",
        *,
        approved: bool,
        paired_at: int | None = None,
    ) -> PairingRecord:
        """Persist a pairing only after the local caller explicitly approved it.

        Re-pairing a previously revoked key is permitted only with a new explicit
        approval; it creates a fresh active record and resets the old revoke
        timestamp. The caller must not derive ``approved`` from any Relay input.
        """
        if approved is not True:
            raise PermissionError("local operator approval is required to pair")
        normalized = _normalize_pubkey(pubkey)
        label = _validate_label(label)
        paired_at = _timestamp(paired_at, "paired_at")

        with self._lock:
            self._connection.execute(
                """
                INSERT INTO nostr_remote_pairings (pubkey, label, paired_at, revoked_at)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(pubkey) DO UPDATE SET
                    label = excluded.label,
                    paired_at = excluded.paired_at,
                    revoked_at = NULL
                """,
                (normalized, label, paired_at),
            )
            row = self._connection.execute(
                "SELECT pubkey, label, paired_at, revoked_at "
                "FROM nostr_remote_pairings WHERE pubkey = ?",
                (normalized,),
            ).fetchone()
        return PairingRecord(*row)

    def revoke(self, pubkey: str, *, revoked_at: int | None = None) -> bool:
        """Immediately revoke an active key; return False for unknown/already revoked keys.

        The caller must expose this operation only behind a local operator
        confirmation. Revoke is idempotent and never deletes the audit record.
        """
        normalized = _normalize_pubkey(pubkey)
        revoked_at = _timestamp(revoked_at, "revoked_at")
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE nostr_remote_pairings SET revoked_at = ? "
                "WHERE pubkey = ? AND revoked_at IS NULL",
                (revoked_at, normalized),
            )
            return cursor.rowcount == 1

    def is_authorized(self, pubkey: str) -> bool:
        """Return whether a key is currently paired; malformed keys fail closed."""
        try:
            normalized = _normalize_pubkey(pubkey)
        except ValueError:
            return False
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM nostr_remote_pairings "
                "WHERE pubkey = ? AND revoked_at IS NULL",
                (normalized,),
            ).fetchone()
        return row is not None

    def list_devices(self, *, include_revoked: bool = False) -> list[PairingRecord]:
        """Return public pairing metadata, excluding revoked devices by default."""
        if not isinstance(include_revoked, bool):
            raise TypeError("include_revoked must be bool")
        query = (
            "SELECT pubkey, label, paired_at, revoked_at " "FROM nostr_remote_pairings"
        )
        if not include_revoked:
            query += " WHERE revoked_at IS NULL"
        query += " ORDER BY paired_at, pubkey"
        with self._lock:
            rows = self._connection.execute(query).fetchall()
        return [PairingRecord(*row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLitePairingStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
