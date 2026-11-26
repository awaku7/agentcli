"""Local pairing registry for BitChat peers (BLE Noise + linked Nostr).

One record per person, mirroring upstream BitChat's FavoriteRelationship:
the record is keyed by the peer's Noise static public key (the identity a
completed Noise XX handshake actually verifies) and may carry one linked
Nostr public key, so a peer paired in person over BLE can also reach the
node over Nostr DMs.

Pairing is a local operator action only: ``pair()`` refuses to run without
explicit approval, exactly like the Nostr remote pairing store. Nothing in
the receive paths may create or extend a record — an incoming message can
only *consult* the registry.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MAX_LABEL_BYTES = 200


def _normalize_key(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    key = value.strip().lower()
    if len(key) != 64:
        raise ValueError(f"{field} must be 64 hex characters")
    try:
        bytes.fromhex(key)
    except ValueError as exc:
        raise ValueError(f"{field} must be 64 hex characters") from exc
    return key


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


CHAT_BINDINGS = ("attach", "room")
_MAX_ROOM_SESSION_ID_CHARS = 128


def _validate_binding(binding: str) -> str:
    if binding not in CHAT_BINDINGS:
        raise ValueError("binding must be 'attach' or 'room'")
    return binding


def _validate_room_session_id(session_id: str) -> str:
    if (
        not isinstance(session_id, str)
        or not session_id
        or len(session_id) > _MAX_ROOM_SESSION_ID_CHARS
        or "\x00" in session_id
    ):
        raise ValueError(
            "room session id must be a non-empty string of at most "
            f"{_MAX_ROOM_SESSION_ID_CHARS} characters"
        )
    return session_id


@dataclass(frozen=True)
class BitchatPairingRecord:
    """One paired BitChat peer; ``revoked_at`` is set after revocation.

    ``binding`` decides where the peer's llm-mode conversation
    lives: ``attach`` joins the operator's current (main) session,
    ``room`` gives the peer its own session (``room_session_id``,
    assigned on first use).
    """

    noise_key: str
    nostr_key: str | None
    label: str
    paired_at: int
    revoked_at: int | None
    binding: str = "attach"
    room_session_id: str | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None


class SQLiteBitchatPairingStore:
    """SQLite persistence for BitChat peer pairing and immediate revocation.

    Authorization checks are cheap lookups meant to be called for every
    incoming DM rather than cached, so a revocation takes effect at once.
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
            CREATE TABLE IF NOT EXISTS bitchat_pairings (
                noise_key TEXT PRIMARY KEY,
                nostr_key TEXT,
                label TEXT NOT NULL,
                paired_at INTEGER NOT NULL,
                revoked_at INTEGER
            )
            """)
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_bitchat_pairings_nostr "
            "ON bitchat_pairings (nostr_key)"
        )
        columns = {
            row[1]
            for row in self._connection.execute(
                "PRAGMA table_info(bitchat_pairings)"
            ).fetchall()
        }
        if "binding" not in columns:
            self._connection.execute(
                "ALTER TABLE bitchat_pairings "
                "ADD COLUMN binding TEXT NOT NULL DEFAULT 'attach'"
            )
        if "room_session_id" not in columns:
            self._connection.execute(
                "ALTER TABLE bitchat_pairings ADD COLUMN room_session_id TEXT"
            )

    # -- operator actions (local console only) --

    def pair(
        self,
        noise_key: str,
        label: str = "",
        *,
        approved: bool = False,
        paired_at: int | None = None,
        binding: str = "attach",
    ) -> BitchatPairingRecord:
        """Create or reactivate a pairing for ``noise_key``.

        Reactivating a revoked record clears any Nostr link it had:
        re-pairing is a fresh operator decision, so Nostr access must be
        linked again explicitly. It likewise resets the chat
        ``binding`` (to the given value, default ``attach``) and
        clears any room session assigned under the old pairing.
        ``approved`` must be True: pairing grants LLM access, so it
        may only happen as an explicit local operator action.
        """
        if not approved:
            raise PermissionError("local operator approval is required to pair")
        key = _normalize_key(noise_key, "noise_key")
        clean_label = _validate_label(label)
        clean_binding = _validate_binding(binding)
        when = int(time.time()) if paired_at is None else int(paired_at)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO bitchat_pairings (
                    noise_key, nostr_key, label, paired_at, revoked_at,
                    binding, room_session_id
                )
                VALUES (?, NULL, ?, ?, NULL, ?, NULL)
                ON CONFLICT(noise_key) DO UPDATE SET
                    label = excluded.label,
                    paired_at = excluded.paired_at,
                    nostr_key = NULL,
                    revoked_at = NULL,
                    binding = excluded.binding,
                    room_session_id = NULL
                """,
                (key, clean_label, when, clean_binding),
            )
        record = self._get(key)
        assert record is not None
        return record

    def set_binding(self, noise_key: str, binding: str) -> bool:
        """Change an active pairing's chat binding; False if not active."""
        key = _normalize_key(noise_key, "noise_key")
        clean_binding = _validate_binding(binding)
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE bitchat_pairings SET binding = ? "
                "WHERE noise_key = ? AND revoked_at IS NULL",
                (clean_binding, key),
            )
            return cursor.rowcount == 1

    def assign_room_session_id(self, noise_key: str, session_id: str) -> bool:
        """Overwrite an active pairing's room session id.

        Used when the recorded room session no longer exists (for
        example it was deleted), so the peer gets a fresh room.
        """
        key = _normalize_key(noise_key, "noise_key")
        clean_session_id = _validate_room_session_id(session_id)
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE bitchat_pairings SET room_session_id = ? "
                "WHERE noise_key = ? AND revoked_at IS NULL",
                (clean_session_id, key),
            )
            return cursor.rowcount == 1

    def ensure_room_session_id(self, noise_key: str, new_session_id: str) -> str | None:
        """Return the pairing's room session id, assigning one if unset.

        The first session id offered for an active pairing sticks, so
        a peer's room is stable across restarts. Returns None when
        there is no active pairing for the key.
        """
        try:
            key = _normalize_key(noise_key, "noise_key")
        except (TypeError, ValueError):
            return None
        clean_session_id = _validate_room_session_id(new_session_id)
        with self._lock:
            row = self._connection.execute(
                "SELECT room_session_id FROM bitchat_pairings "
                "WHERE noise_key = ? AND revoked_at IS NULL",
                (key,),
            ).fetchone()
            if row is None:
                return None
            if row[0]:
                return str(row[0])
            self._connection.execute(
                "UPDATE bitchat_pairings SET room_session_id = ? "
                "WHERE noise_key = ? AND room_session_id IS NULL",
                (clean_session_id, key),
            )
            return clean_session_id

    def record_for_nostr(self, nostr_key: str) -> BitchatPairingRecord | None:
        """Return the pairing record linked to ``nostr_key``, or None."""
        try:
            key = _normalize_key(nostr_key, "nostr_key")
        except (TypeError, ValueError):
            return None
        with self._lock:
            row = self._connection.execute(
                "SELECT noise_key, nostr_key, label, paired_at, revoked_at, "
                "binding, room_session_id "
                "FROM bitchat_pairings WHERE nostr_key = ? "
                "AND revoked_at IS NULL ORDER BY paired_at DESC LIMIT 1",
                (key,),
            ).fetchone()
        return BitchatPairingRecord(*row) if row is not None else None

    def link_nostr(
        self,
        noise_key: str,
        nostr_key: str,
        *,
        approved: bool = False,
    ) -> BitchatPairingRecord:
        """Link a Nostr pubkey to an existing active pairing."""
        if not approved:
            raise PermissionError("local operator approval is required to link")
        key = _normalize_key(noise_key, "noise_key")
        linked = _normalize_key(nostr_key, "nostr_key")
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE bitchat_pairings SET nostr_key = ? "
                "WHERE noise_key = ? AND revoked_at IS NULL",
                (linked, key),
            )
            if cursor.rowcount == 0:
                raise ValueError("no active pairing for that Noise key")
        record = self._get(key)
        assert record is not None
        return record

    def record_for(self, noise_key: str) -> BitchatPairingRecord | None:
        """Return the pairing record for ``noise_key``, or None."""
        try:
            key = _normalize_key(noise_key, "noise_key")
        except (TypeError, ValueError):
            return None
        return self._get(key)

    def apply_favorite_claim(
        self, noise_key: str, nostr_key: str | None, *, favorited: bool
    ) -> str:
        """Apply a BitChat favorite notification from the Noise channel.

        Real BitChat clients send ``[FAVORITED]:<npub>`` as a Noise DM
        when the user favorites a peer; because it rides the encrypted
        Noise session, the sender is cryptographically the holder of
        ``noise_key``, so the claimed Nostr key can be linked without a
        manual ``:bitchat link``. Only an empty link slot is filled — a
        different already-linked key is never overwritten by a claim
        (replacing it stays a manual operator decision). An unfavorite
        removes the link only when it matches the claimed key.

        Returns "linked", "unlinked", "already", "conflict", "unpaired"
        or "noop".
        """
        try:
            key = _normalize_key(noise_key, "noise_key")
            linked = _normalize_key(nostr_key, "nostr_key") if nostr_key else None
        except (TypeError, ValueError):
            return "noop"
        record = self._get(key)
        if record is None or not record.active:
            return "unpaired"
        if favorited:
            if linked is None:
                return "noop"
            if record.nostr_key is None:
                with self._lock:
                    self._connection.execute(
                        "UPDATE bitchat_pairings SET nostr_key = ? "
                        "WHERE noise_key = ? AND revoked_at IS NULL",
                        (linked, key),
                    )
                return "linked"
            return "already" if record.nostr_key == linked else "conflict"
        # Unfavorite: drop the link only when the claim names it (or the
        # claim carries no key at all, which upstream sends when the
        # peer has no Nostr identity to name).
        if record.nostr_key is not None and (
            linked is None or record.nostr_key == linked
        ):
            with self._lock:
                self._connection.execute(
                    "UPDATE bitchat_pairings SET nostr_key = NULL "
                    "WHERE noise_key = ? AND revoked_at IS NULL",
                    (key,),
                )
            return "unlinked"
        return "noop"

    def revoke(self, noise_key: str, *, revoked_at: int | None = None) -> bool:
        key = _normalize_key(noise_key, "noise_key")
        when = int(time.time()) if revoked_at is None else int(revoked_at)
        with self._lock:
            cursor = self._connection.execute(
                "UPDATE bitchat_pairings SET revoked_at = ? "
                "WHERE noise_key = ? AND revoked_at IS NULL",
                (when, key),
            )
            return cursor.rowcount > 0

    # -- authorization lookups (receive paths) --

    def is_authorized_noise(self, noise_key: str) -> bool:
        try:
            key = _normalize_key(noise_key, "noise_key")
        except (TypeError, ValueError):
            return False
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM bitchat_pairings "
                "WHERE noise_key = ? AND revoked_at IS NULL",
                (key,),
            ).fetchone()
        return row is not None

    def is_authorized_nostr(self, nostr_key: str) -> bool:
        """True when ``nostr_key`` is linked to an active BLE pairing."""
        try:
            key = _normalize_key(nostr_key, "nostr_key")
        except (TypeError, ValueError):
            return False
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM bitchat_pairings "
                "WHERE nostr_key = ? AND revoked_at IS NULL",
                (key,),
            ).fetchone()
        return row is not None

    def list_devices(
        self, *, include_revoked: bool = False
    ) -> list[BitchatPairingRecord]:
        query = (
            "SELECT noise_key, nostr_key, label, paired_at, revoked_at, "
            "binding, room_session_id "
            "FROM bitchat_pairings"
        )
        if not include_revoked:
            query += " WHERE revoked_at IS NULL"
        query += " ORDER BY paired_at"
        with self._lock:
            rows = self._connection.execute(query).fetchall()
        return [BitchatPairingRecord(*row) for row in rows]

    def _get(self, noise_key: str) -> BitchatPairingRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT noise_key, nostr_key, label, paired_at, revoked_at, "
                "binding, room_session_id "
                "FROM bitchat_pairings WHERE noise_key = ?",
                (noise_key,),
            ).fetchone()
        return BitchatPairingRecord(*row) if row is not None else None

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteBitchatPairingStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def bitchat_pairing_database_path() -> Path:
    """Return the BitChat pairing registry path under UAG's database dir."""
    from .utils.paths import get_dbs_dir

    return get_dbs_dir() / "bitchat_pairings.sqlite3"


def open_bitchat_pairing_store() -> SQLiteBitchatPairingStore:
    """Open the shared BitChat pairing registry, creating its directory."""
    path = bitchat_pairing_database_path()
    os.makedirs(os.path.dirname(os.fspath(path)), exist_ok=True)
    return SQLiteBitchatPairingStore(path)
