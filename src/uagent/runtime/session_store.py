"""SQLite-backed session, message, and tool-call persistence."""

from __future__ import annotations

import atexit
import hashlib
import json
import ntpath
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..utils.paths import get_state_dir
from ..utils.secret_mask import mask_args
from .compaction_record import CompactionRecord, CompactionValidationError, SourceRef
from .handoff_record import HandoffRecord, ProvenancedDeterministicDelta
from .compaction_reducer import CompactionReductionError, reduce_compaction_record
from .tool_result_persistence import (
    sanitize_binary_payload,
    sanitize_message_for_history,
)


class SessionStoreError(RuntimeError):
    """Raised when session persistence cannot complete safely."""


class SessionRevisionConflict(SessionStoreError):
    """Raised when an expected AgentState revision is no longer current."""


class SessionComparisonUnavailable(SessionStoreError):
    """Raised when comparison-only needs an AgentState snapshot we did not retain."""


_SQLITE_LOCK_RETRIES = 3
_SQLITE_LOCK_RETRY_DELAY = 0.25
_SESSION_ITEM_KINDS = {
    "message",
    "tool_call",
    "tool_result",
    "runtime_event",
    "execution",
    "artifact_link",
    "checkpoint",
    "handoff",
    "subagent_result",
}
_SESSION_ITEM_ORDERING_QUALITIES = {
    "exact",
    "legacy_message_order",
    "legacy_approximate",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_locked(method):
    """Serialize access to the shared SQLite connection."""

    def wrapper(self, *args, **kwargs):
        with self._db_lock:
            return method(self, *args, **kwargs)

    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


@dataclass(frozen=True)
class Session:
    session_id: str
    project: str | None
    entry_point: str
    project_key: str = ""
    project_path: str | None = None


_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(\b(?:token|password|passwd|api[_-]?key|secret)\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)(\bCookie\s*:\s*)([^\r\n]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]+\b"),
)


def project_id_from_path(path: str | Path) -> str:
    """Return a stable, human-friendly workspace name from a path."""
    raw = str(path).rstrip("\\/")
    name = ntpath.basename(raw) or os.path.basename(raw)
    return name or raw or "workspace"


def normalize_tool_call(call: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Normalize OpenAI-style and flat tool-call payloads for persistence."""
    call_id = str(call.get("id") or call.get("tool_call_id") or "")
    function = call.get("function")
    if isinstance(function, dict):
        name = str(function.get("name") or call.get("name") or "tool")
        raw_args = function.get("arguments", {})
    else:
        name = str(call.get("name") or "tool")
        raw_args = call.get("arguments", call.get("args", {}))
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except (TypeError, ValueError):
            raw_args = {"_raw": raw_args}
    if not isinstance(raw_args, dict):
        raw_args = {"_raw": raw_args}
    return call_id, name, raw_args


def redact_sensitive(text: str) -> str:
    """Remove common credential values without attempting to parse secrets."""
    result = text
    for pattern in _SECRET_PATTERNS[:2]:
        result = pattern.sub(r"\1[REDACTED]", result)
    return _SECRET_PATTERNS[2].sub("[REDACTED]", result)


def _sanitize_text(value: Any) -> Any:
    """Return a SQLite-safe string (fold surrogate pairs, drop lone surrogates).

    Windows console/clipboard input and broken UTF-16 decodes can produce
    lone surrogates (U+D800..U+DFFF). CPython's sqlite3 driver encodes
    parameters as UTF-8 with strict errors, so such strings raise
    ``UnicodeEncodeError: surrogates not allowed`` and crash the CLI
    (see ``append_message`` INSERT). Folding via UTF-16 keeps valid pairs
    (e.g. emoji split into two surrogates) intact and replaces lone
    surrogates with U+FFFD.
    """
    if not isinstance(value, str):
        return value
    if not value:
        return value
    # Fast path: no surrogates present.
    has_surrogate = False
    for ch in value:
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            has_surrogate = True
            break
    if not has_surrogate:
        return value
    try:
        return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    except Exception:
        return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in value)


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize str keys/values so JSON dumps stay UTF-8 safe."""
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, dict):
        return {
            _sanitize_value(key) if isinstance(key, str) else key: _sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        cleaned = [_sanitize_value(item) for item in value]
        return type(value)(cleaned) if isinstance(value, tuple) else cleaned
    return value


def _safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """json.dumps with surrogate sanitization (input and output)."""
    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("sort_keys", True)
    try:
        text = json.dumps(_sanitize_value(obj), **kwargs)
    except (TypeError, ValueError):
        raise
    return _sanitize_text(text)


def _migrate_legacy_session_store(path: Path) -> None:
    """Move the legacy default store to the current ``.uag`` location."""
    current = Path(".uag/sessions.sqlite3").absolute()
    if path.absolute() != current:
        return

    legacy = Path(".uagent/sessions.sqlite3")
    if not legacy.exists():
        _remove_empty_legacy_dir(legacy)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        # The current database wins when both locations exist.
        legacy.unlink()
        for suffix in ("-wal", "-shm"):
            legacy.with_name(legacy.name + suffix).unlink(missing_ok=True)
        _remove_empty_legacy_dir(legacy)
        return

    os.replace(legacy, path)
    # Keep SQLite sidecar files together with the database when present.
    for suffix in ("-wal", "-shm"):
        old_sidecar = legacy.with_name(legacy.name + suffix)
        if old_sidecar.exists():
            os.replace(old_sidecar, path.with_name(path.name + suffix))
    _remove_empty_legacy_dir(legacy)


def _remove_empty_legacy_dir(legacy: Path) -> None:
    """Remove the legacy directory when migration left it empty."""
    try:
        legacy.parent.rmdir()
    except OSError:
        pass


def _remove_global_artifact_dirs(stored_paths: list[str]) -> None:
    """Best-effort cleanup for new global artifacts after session deletion.

    Only the current global artifact layout (``<id>/<name>``) is eligible.
    Legacy workdir-relative paths and absolute paths are intentionally left
    untouched because this module cannot safely determine their owner root.
    """
    root = (get_state_dir() / "artifacts").expanduser().absolute().resolve()
    for stored_path in stored_paths:
        path = Path(str(stored_path))
        if path.is_absolute() or len(path.parts) < 2:
            continue
        artifact_id = path.parts[0]
        if re.fullmatch(r"[0-9a-f]{32}", artifact_id) is None:
            continue
        artifact_dir = (root / artifact_id).resolve()
        try:
            artifact_dir.relative_to(root)
        except ValueError:
            continue
        if artifact_dir == root or not artifact_dir.is_dir():
            continue
        shutil.rmtree(artifact_dir, ignore_errors=True)


class SessionStore:
    """Small repository for durable session data.

    The class owns one SQLite connection per instance. It intentionally stores
    redacted text only and uses parameterized SQL for all user-controlled data.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        try:
            # Multiple CLI/Web/A2A processes may share one store. WAL lets
            # readers proceed while a writer commits, and the longer busy
            # timeout avoids failing on normal short-lived writer contention.
            self._connection = sqlite3.connect(
                self.path, timeout=5.0, isolation_level=None, check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self._initialize()
        except sqlite3.Error as exc:
            raise SessionStoreError(f"could not open session store: {exc}") from exc

    @classmethod
    def from_environment(cls) -> "SessionStore | None":
        """Create a store unless explicitly disabled by the environment."""
        enabled = os.environ.get("UAGENT_SESSION_STORE", "1").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return None
        path = os.environ.get("UAGENT_SESSION_STORE_PATH", "").strip()
        if path:
            store_path = Path(path)
        else:
            # New installations use the global state directory. Only the
            # older .uagent location gets compatibility migration; an
            # existing .uag directory must not make the workdir stateful.
            legacy_store = Path(".uagent/sessions.sqlite3")
            store_path = (
                Path(".uag/sessions.sqlite3")
                if legacy_store.exists()
                else get_state_dir() / "sessions" / "sessions.sqlite3"
            )
        try:
            _migrate_legacy_session_store(store_path)
        except OSError as exc:
            raise SessionStoreError(
                f"could not migrate legacy session store: {exc}"
            ) from exc
        return cls(store_path)

    def close(self) -> None:
        # ToolCallbacks is process-wide, so a direct close (not only the
        # entry-point detach path) must not leave a closed store available to
        # later tool calls.
        try:
            from ..tools.context import get_callbacks

            callbacks = get_callbacks()
            if getattr(callbacks, "session_store", None) is self:
                callbacks.session_store = None
                callbacks.session_id = None
        except Exception:
            pass
        with self._db_lock:
            self._connection.close()

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _initialize(self) -> None:
        try:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    project TEXT,
                    project_key TEXT NOT NULL,
                    project_path TEXT,
                    entry_point TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    principal_id TEXT,
                    room_id TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS session_items (
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    session_seq INTEGER NOT NULL CHECK(session_seq > 0),
                    item_kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    ordering_quality TEXT NOT NULL CHECK(ordering_quality IN (
                        'exact', 'legacy_message_order', 'legacy_approximate'
                    )),
                    availability TEXT NOT NULL DEFAULT 'available' CHECK(availability IN (
                        'available', 'unavailable'
                    )),
                    PRIMARY KEY(session_id, session_seq),
                    UNIQUE(session_id, item_kind, item_id)
                );
                CREATE TABLE IF NOT EXISTS portable_sessions (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    call_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    result TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
                    content, session_id UNINDEXED, message_id UNINDEXED
                );
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS response_states (
                    state_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    response_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS tool_context_states (
                    context_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    tool_name TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS tool_results (
                    result_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    task_id TEXT,
                    tool_name TEXT NOT NULL,
                    result_class TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    artifact_ref TEXT,
                    importance TEXT NOT NULL,
                    evictable INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    persistent_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_states (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    updated_by_client TEXT
                );
                CREATE TABLE IF NOT EXISTS sub_agent_receipts (
                    root_handoff_id TEXT PRIMARY KEY,
                    receiving_session_id TEXT NOT NULL
                        REFERENCES sessions(session_id) ON DELETE CASCADE,
                    source_session_id TEXT NOT NULL,
                    base_revision INTEGER NOT NULL CHECK(base_revision >= 0),
                    record_json TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sub_agent_receipts_receiver
                    ON sub_agent_receipts(receiving_session_id, received_at);
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL UNIQUE,
                    application_status TEXT NOT NULL CHECK(application_status IN (
                        'applied', 'comparison_only'
                    )),
                    actor_kind TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    base_revision INTEGER NOT NULL CHECK(base_revision >= 0),
                    result_revision INTEGER,
                    source_start_seq INTEGER NOT NULL CHECK(source_start_seq > 0),
                    source_end_seq INTEGER NOT NULL CHECK(source_end_seq >= source_start_seq),
                    schema_version INTEGER NOT NULL,
                    parent_checkpoint_id TEXT REFERENCES checkpoints(checkpoint_id),
                    record_json TEXT NOT NULL,
                    created_by_client TEXT,
                    created_at TEXT NOT NULL,
                    CHECK(
                        (application_status = 'applied' AND result_revision = base_revision + 1)
                        OR (application_status = 'comparison_only' AND result_revision IS NULL)
                    )
                );
                CREATE TABLE IF NOT EXISTS policy_decisions (
                    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    tool_call_id TEXT,
                    tool_name TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS context_decisions (
                    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    section TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    importance REAL,
                    original_chars INTEGER,
                    projected_chars INTEGER,
                    reference TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS legacy_imports (
                    source_path TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_created
                    ON sessions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_project_created
                    ON sessions(project, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                    ON messages(session_id, message_id);
                CREATE INDEX IF NOT EXISTS idx_session_items_kind_seq
                    ON session_items(session_id, item_kind, session_seq);
                CREATE INDEX IF NOT EXISTS idx_response_states_session_id
                    ON response_states(session_id, state_id);
                CREATE INDEX IF NOT EXISTS idx_tool_context_states_session_id
                    ON tool_context_states(session_id, context_id);
                CREATE INDEX IF NOT EXISTS idx_tool_results_session_created
                    ON tool_results(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_messages_session_role_id
                    ON messages(session_id, role, message_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_session_created
                    ON tool_calls(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_policy_decisions_session_id
                    ON policy_decisions(session_id, decision_id);
                CREATE INDEX IF NOT EXISTS idx_context_decisions_session_id
                    ON context_decisions(session_id, decision_id);
                """)
            columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(sessions)")
            }
            if "project_key" not in columns:
                self._connection.execute(
                    "ALTER TABLE sessions ADD COLUMN project_key TEXT NOT NULL DEFAULT 'legacy'"
                )
            if "project_path" not in columns:
                self._connection.execute(
                    "ALTER TABLE sessions ADD COLUMN project_path TEXT"
                )
            if "last_used_at" not in columns:
                self._connection.execute(
                    "ALTER TABLE sessions ADD COLUMN last_used_at TEXT"
                )
                # Legacy stores used ``created_at`` as a recency timestamp when
                # a session was loaded. Preserve that value as last-used time,
                # then recover the original session date from the first durable
                # message only when it predates the stored recency value.
                self._connection.execute(
                    "UPDATE sessions SET last_used_at = created_at WHERE last_used_at IS NULL"
                )
                self._connection.execute(
                    "UPDATE sessions SET created_at = ("
                    "SELECT MIN(m.created_at) FROM messages m "
                    "WHERE m.session_id = sessions.session_id"
                    ") WHERE EXISTS ("
                    "SELECT 1 FROM messages m WHERE m.session_id = sessions.session_id "
                    "AND m.created_at < sessions.created_at"
                    ")"
                )
            if "principal_id" not in columns:
                self._connection.execute(
                    "ALTER TABLE sessions ADD COLUMN principal_id TEXT"
                )
            if "room_id" not in columns:
                self._connection.execute("ALTER TABLE sessions ADD COLUMN room_id TEXT")
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_last_used "
                "ON sessions(last_used_at DESC)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_project_last_used "
                "ON sessions(project, last_used_at DESC)"
            )
            message_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(messages)")
            }
            if "payload_json" not in message_columns:
                self._connection.execute(
                    "ALTER TABLE messages ADD COLUMN payload_json TEXT"
                )
            tool_result_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(tool_results)")
            }
            if "metadata_json" not in tool_result_columns:
                self._connection.execute(
                    "ALTER TABLE tool_results ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
                )
            agent_state_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(agent_states)")
            }
            if "revision" not in agent_state_columns:
                self._connection.execute(
                    "ALTER TABLE agent_states ADD COLUMN revision INTEGER NOT NULL DEFAULT 0"
                )
            if "updated_by_client" not in agent_state_columns:
                self._connection.execute(
                    "ALTER TABLE agent_states ADD COLUMN updated_by_client TEXT"
                )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_checkpoints_session_created "
                "ON checkpoints(session_id, created_at, checkpoint_id)"
            )
            self._backfill_session_items()
        except sqlite3.Error as exc:
            raise SessionStoreError(
                f"could not initialize session store: {exc}"
            ) from exc

    def _execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        # Safety net: lone surrogates (Windows console/clipboard, broken
        # UTF-16) crash sqlite3 with UnicodeEncodeError since it encodes
        # parameters as strict UTF-8. Sanitize here so every current and
        # future caller is protected even if it forgets to sanitize.
        if parameters:
            parameters = tuple(
                _sanitize_text(p) if isinstance(p, str) else p for p in parameters
            )
        for attempt in range(_SQLITE_LOCK_RETRIES + 1):
            try:
                return self._connection.execute(sql, parameters)
            except sqlite3.OperationalError as exc:
                # A different CLI/Web/A2A process can briefly hold the shared
                # session database while committing. SQLite's busy timeout is
                # necessary but not sufficient when a writer is finishing a
                # longer transaction; retry the statement before failing the
                # current interaction.
                if "locked" in str(exc).lower() and attempt < _SQLITE_LOCK_RETRIES:
                    time.sleep(_SQLITE_LOCK_RETRY_DELAY * (2**attempt))
                    continue
                raise SessionStoreError(
                    f"session store operation failed: {exc}"
                ) from exc
            except sqlite3.Error as exc:
                raise SessionStoreError(
                    f"session store operation failed: {exc}"
                ) from exc
        raise AssertionError("unreachable sqlite retry state")

    def _require_session(self, session_id: str) -> None:
        row = self._execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise SessionStoreError(f"unknown session: {session_id}")

    def _record_session_item_unlocked(
        self,
        session_id: str,
        item_kind: str,
        item_id: str,
        *,
        ordering_quality: str = "exact",
        session_seq: int | None = None,
    ) -> int:
        """Index one source item while the caller owns a write transaction."""
        self._require_session(session_id)
        kind = str(item_kind or "").strip()
        stable_id = str(item_id or "").strip()
        if kind not in _SESSION_ITEM_KINDS:
            raise ValueError(f"invalid session item kind: {kind}")
        if not stable_id:
            raise ValueError("session item ID is empty")
        if ordering_quality not in _SESSION_ITEM_ORDERING_QUALITIES:
            raise ValueError(
                f"invalid session item ordering quality: {ordering_quality}"
            )

        existing = self._execute(
            "SELECT session_seq, availability FROM session_items "
            "WHERE session_id = ? AND item_kind = ? AND item_id = ?",
            (session_id, kind, stable_id),
        ).fetchone()
        if existing is not None:
            if existing["availability"] != "available":
                raise SessionStoreError("unavailable session item IDs cannot be reused")
            return int(existing["session_seq"])

        if session_seq is None:
            row = self._execute(
                "SELECT COALESCE(MAX(session_seq), 0) + 1 AS next_seq "
                "FROM session_items WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            session_seq = int(row["next_seq"])
        elif (
            isinstance(session_seq, bool)
            or not isinstance(session_seq, int)
            or session_seq <= 0
        ):
            raise ValueError("session_seq must be a positive integer")

        self._execute(
            "INSERT INTO session_items(session_id, session_seq, item_kind, item_id, "
            "ordering_quality, availability) VALUES (?, ?, ?, ?, ?, 'available')",
            (session_id, session_seq, kind, stable_id, ordering_quality),
        )
        return session_seq

    def _backfill_session_items(self) -> None:
        """Backfill stable message order and conservatively mark unlinked rows."""
        sessions = self._connection.execute(
            "SELECT s.session_id FROM sessions s WHERE "
            "EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.session_id "
            "AND NOT EXISTS (SELECT 1 FROM session_items i WHERE "
            "i.session_id = m.session_id AND i.item_kind = 'message' "
            "AND i.item_id = CAST(m.message_id AS TEXT))) OR "
            "EXISTS (SELECT 1 FROM tool_calls t WHERE t.session_id = s.session_id "
            "AND NOT EXISTS (SELECT 1 FROM session_items i WHERE "
            "i.session_id = t.session_id AND i.item_kind = 'tool_call' "
            "AND i.item_id = t.call_id)) OR "
            "EXISTS (SELECT 1 FROM tool_results r WHERE r.session_id = s.session_id "
            "AND NOT EXISTS (SELECT 1 FROM session_items i WHERE "
            "i.session_id = r.session_id AND i.item_kind = 'tool_result' "
            "AND i.item_id = r.result_id)) ORDER BY s.session_id"
        ).fetchall()
        for session_row in sessions:
            session_id = str(session_row["session_id"])
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                max_row = self._execute(
                    "SELECT COALESCE(MAX(session_seq), 0) AS max_seq "
                    "FROM session_items WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                next_seq = int(max_row["max_seq"]) + 1

                def index_legacy(kind: str, item_id: str, quality: str) -> None:
                    nonlocal next_seq
                    exists = self._execute(
                        "SELECT 1 FROM session_items "
                        "WHERE session_id = ? AND item_kind = ? AND item_id = ?",
                        (session_id, kind, item_id),
                    ).fetchone()
                    if exists is not None:
                        return
                    self._record_session_item_unlocked(
                        session_id,
                        kind,
                        item_id,
                        ordering_quality=quality,
                        session_seq=next_seq,
                    )
                    next_seq += 1

                result_rows = self._execute(
                    "SELECT result_id, metadata_json, created_at FROM tool_results "
                    "WHERE session_id = ? ORDER BY created_at, result_id",
                    (session_id,),
                ).fetchall()
                results_by_call: dict[str, list[str]] = {}
                for result_row in result_rows:
                    try:
                        metadata = json.loads(result_row["metadata_json"] or "{}")
                    except (TypeError, ValueError):
                        metadata = {}
                    call_id = (
                        str(metadata.get("tool_call_id") or "")
                        if isinstance(metadata, dict)
                        else ""
                    )
                    if call_id:
                        results_by_call.setdefault(call_id, []).append(
                            str(result_row["result_id"])
                        )

                indexed_results: set[str] = set()
                message_rows = self._execute(
                    "SELECT message_id, role, payload_json FROM messages "
                    "WHERE session_id = ? ORDER BY message_id",
                    (session_id,),
                ).fetchall()
                for message_row in message_rows:
                    role = str(message_row["role"] or "")
                    try:
                        payload = json.loads(message_row["payload_json"] or "{}")
                    except (TypeError, ValueError):
                        payload = {}
                    if not isinstance(payload, dict):
                        payload = {}

                    if role == "tool":
                        call_id = str(payload.get("tool_call_id") or "")
                        for result_id in results_by_call.get(call_id, []):
                            index_legacy(
                                "tool_result", result_id, "legacy_message_order"
                            )
                            indexed_results.add(result_id)

                    index_legacy(
                        "message",
                        str(message_row["message_id"]),
                        "legacy_message_order",
                    )

                    if role == "assistant":
                        for raw_call in payload.get("tool_calls") or []:
                            if not isinstance(raw_call, dict):
                                continue
                            call_id, _name, _args = normalize_tool_call(raw_call)
                            if call_id:
                                index_legacy(
                                    "tool_call", call_id, "legacy_message_order"
                                )

                call_rows = self._execute(
                    "SELECT call_id FROM tool_calls WHERE session_id = ? "
                    "ORDER BY created_at, rowid",
                    (session_id,),
                ).fetchall()
                for call_row in call_rows:
                    index_legacy(
                        "tool_call", str(call_row["call_id"]), "legacy_approximate"
                    )
                for result_row in result_rows:
                    result_id = str(result_row["result_id"])
                    if result_id not in indexed_results:
                        index_legacy("tool_result", result_id, "legacy_approximate")

                self._connection.execute("COMMIT")
            except Exception:
                try:
                    self._connection.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    @_db_locked
    def record_session_item(self, session_id: str, item_kind: str, item_id: str) -> int:
        """Append a runtime-observed source item to the ordered session index."""
        self._require_session(session_id)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            session_seq = self._record_session_item_unlocked(
                session_id, item_kind, item_id
            )
            self._connection.execute("COMMIT")
            return session_seq
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def get_session_item_watermark(self, session_id: str) -> int:
        """Return the highest allocated session_seq, or zero for an empty session."""
        self._require_session(session_id)
        row = self._execute(
            "SELECT COALESCE(MAX(session_seq), 0) AS watermark "
            "FROM session_items WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["watermark"])

    @_db_locked
    def list_session_items(
        self,
        session_id: str,
        *,
        start_seq: int,
        end_seq: int | None = None,
        require_exact_order: bool = True,
        require_available: bool = True,
    ) -> list[dict[str, Any]]:
        """List source-index metadata for an inclusive, fixed session range.

        Callers should capture ``end_seq`` from ``get_session_item_watermark``
        before building a compaction request. Legacy rows whose cross-table
        order cannot be reconstructed, and source items that were replaced or
        evicted, are rejected by default so callers can use the legacy fallback.
        """
        self._require_session(session_id)
        if (
            isinstance(start_seq, bool)
            or not isinstance(start_seq, int)
            or start_seq < 0
        ):
            raise ValueError("start_seq must be a non-negative integer")
        watermark = self.get_session_item_watermark(session_id)
        if end_seq is None:
            end_seq = watermark
        if isinstance(end_seq, bool) or not isinstance(end_seq, int) or end_seq < 0:
            raise ValueError("end_seq must be a non-negative integer")
        if end_seq > watermark:
            raise SessionStoreError(
                "source range exceeds the captured session watermark"
            )
        if end_seq < start_seq:
            raise ValueError("end_seq must be greater than or equal to start_seq")

        rows = self._execute(
            "SELECT session_id, session_seq, item_kind, item_id, ordering_quality, "
            "availability FROM session_items WHERE session_id = ? "
            "AND session_seq BETWEEN ? AND ? ORDER BY session_seq",
            (session_id, start_seq, end_seq),
        ).fetchall()
        items = [dict(row) for row in rows]
        if require_exact_order and any(
            item["ordering_quality"] == "legacy_approximate" for item in items
        ):
            raise SessionStoreError(
                "source range contains legacy items with ambiguous ordering"
            )
        if require_available and any(
            item["availability"] != "available" for item in items
        ):
            raise SessionStoreError("source range contains unavailable items")
        return items

    @_db_locked
    def bind_identity_context(
        self, session_id: str, *, principal_id: str, room_id: str
    ) -> None:
        """Bind an existing session once and reject cross-principal reuse."""
        self._require_session(session_id)
        principal = str(principal_id or "").strip()
        room = str(room_id or "").strip()
        if not principal:
            raise SessionStoreError("session principal_id is required")
        row = self._execute(
            "SELECT principal_id, room_id FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        existing_principal = str(row["principal_id"] or "")
        existing_room = str(row["room_id"] or "")
        if existing_principal and existing_principal != principal:
            raise SessionStoreError("session principal mismatch")
        if existing_room and existing_room != room:
            raise SessionStoreError("session room mismatch")
        self._execute(
            "UPDATE sessions SET principal_id = ?, room_id = ? WHERE session_id = ?",
            (principal, room, session_id),
        )

    @_db_locked
    def create_session(
        self,
        *,
        project: str | None,
        entry_point: str,
        project_path: str | Path | None = None,
    ) -> Session:
        session_id = uuid.uuid4().hex
        path_value = str(project_path) if project_path is not None else None
        identity = os.path.normcase(
            os.path.abspath(path_value or project or "workspace")
        )
        project_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        self._execute(
            "INSERT INTO sessions(session_id, project, project_key, project_path, entry_point) VALUES (?, ?, ?, ?, ?)",
            (session_id, project, project_key, path_value, entry_point),
        )
        return Session(session_id, project, entry_point, project_key, path_value)

    @_db_locked
    def get_session(self, session_id: str) -> dict[str, Any]:
        row = self._execute(
            "SELECT session_id, project, project_key, project_path, entry_point, "
            "created_at, last_used_at, principal_id, room_id "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise SessionStoreError(f"unknown session: {session_id}")
        return dict(row)

    @_db_locked
    def get_portable_metadata(self, session_id: str) -> dict[str, Any] | None:
        """Return inert provenance/references, never runtime authorization state."""
        self._require_session(session_id)
        row = self._execute(
            "SELECT metadata_json FROM portable_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    @_db_locked
    def import_portable_payload(
        self, payload: dict[str, Any], *, principal_id: str = ""
    ) -> Session:
        """Atomically create a detached session; the caller supplies local identity.

        Source IDs, project hints and refs are inert provenance. No Memory,
        Room, path, provider state or authorization is restored from the package.
        """
        from .session_portability import validate_payload

        payload = validate_payload(payload)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            session = self.create_session(project=None, entry_point="portable-import")
            if session.session_id == payload["session"]["source_session_id"]:
                raise SessionStoreError("portable session ID collision")
            if principal_id:
                self.bind_identity_context(
                    session.session_id, principal_id=principal_id, room_id=""
                )
            for message in payload["conversation"]:
                self._append_message_unlocked(
                    session.session_id, message["role"], message["content"]
                )
            self._execute(
                "INSERT INTO portable_sessions(session_id, metadata_json) VALUES (?, ?)",
                (
                    session.session_id,
                    _safe_json_dumps(
                        {
                            "session": payload["session"],
                            "references": payload["references"],
                        }
                    ),
                ),
            )
            self._connection.execute("COMMIT")
            return session
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    @_db_locked
    def touch_session(self, session_id: str) -> None:
        """Mark a session as most recently used."""
        self._require_session(session_id)
        self._execute(
            "UPDATE sessions SET last_used_at = strftime('%Y-%m-%d %H:%M:%f', 'now') "
            "WHERE session_id = ?",
            (session_id,),
        )

    def _append_message_unlocked(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> int:
        self._require_session(session_id)
        # Sanitize first: lone surrogates from console/clipboard would
        # otherwise crash sqlite3 (UnicodeEncodeError: surrogates not allowed).
        content = _sanitize_text(
            content if isinstance(content, str) else str(content or "")
        )
        role = _sanitize_text(str(role or ""))
        safe_content = _sanitize_text(redact_sensitive(content))
        safe_payload = None
        if payload is not None:
            try:
                raw_payload_value = _sanitize_value(payload)
                if not isinstance(raw_payload_value, dict):
                    raise TypeError("message payload is not an object")
                safe_payload_value = sanitize_message_for_history(
                    {**raw_payload_value, "role": role}
                )
                safe_payload = _safe_json_dumps(
                    {**safe_payload_value, "content": safe_content},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            except (TypeError, ValueError):
                safe_payload = _safe_json_dumps(
                    {"role": role, "content": safe_content}, ensure_ascii=False
                )
        cursor = self._execute(
            "INSERT INTO messages(session_id, role, content, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, safe_content, safe_payload),
        )
        message_id = int(cursor.lastrowid)
        self._execute(
            "INSERT INTO message_search(content, session_id, message_id) VALUES (?, ?, ?)",
            (safe_content, session_id, message_id),
        )
        self._record_session_item_unlocked(
            session_id, "message", str(message_id), ordering_quality="exact"
        )
        if role == "assistant" and safe_payload:
            try:
                stored_payload = json.loads(safe_payload)
            except (TypeError, ValueError):
                stored_payload = {}
            if isinstance(stored_payload, dict):
                for raw_call in stored_payload.get("tool_calls") or []:
                    if not isinstance(raw_call, dict):
                        continue
                    call_id, _name, _args = normalize_tool_call(raw_call)
                    if call_id:
                        self._record_session_item_unlocked(
                            session_id,
                            "tool_call",
                            call_id,
                            ordering_quality="exact",
                        )
        return message_id

    @_db_locked
    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> int:
        # Keep the source row, FTS index, and ordered source index atomic.
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            message_id = self._append_message_unlocked(
                session_id, role, content, payload=payload
            )
            self._connection.execute("COMMIT")
            return message_id
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def append_sub_agent_result_once(
        self,
        session_id: str,
        content: str,
        *,
        dispatch_id: str,
        job_id: str | None = None,
        compact_report: dict[str, str] | None = None,
    ) -> int:
        """Atomically persist one output per child dispatch across DB connections.

        A retry by the same trusted Job recovers the existing row. Another Job
        cannot claim its output, even if a different Job manager had admitted
        the same dispatch before either Job finished.
        """
        if not isinstance(dispatch_id, str) or not dispatch_id.strip():
            raise SessionStoreError("invalid Sub-Agent dispatch ID")
        if job_id is not None and (not isinstance(job_id, str) or not job_id.strip()):
            raise SessionStoreError("invalid Sub-Agent Job ID")
        payload: dict[str, Any] = {"dispatch_id": dispatch_id}
        if job_id is not None:
            payload["job_id"] = job_id
        if compact_report is not None:
            payload["compact_report"] = compact_report
        try:
            # BEGIN IMMEDIATE serializes checks and inserts across independent
            # SessionStore instances targeting the same SQLite database.
            self._connection.execute("BEGIN IMMEDIATE")
            session = self.get_session(session_id)
            if session["entry_point"] != "sub-agent":
                raise SessionStoreError("Sub-Agent output requires a child session")
            rows = self._execute(
                "SELECT message_id, payload_json FROM messages "
                "WHERE session_id = ? AND role = 'assistant'",
                (session_id,),
            ).fetchall()
            for row in rows:
                try:
                    existing = json.loads(row["payload_json"] or "null")
                except (TypeError, ValueError):
                    continue
                if not isinstance(existing, dict):
                    continue
                if existing.get("dispatch_id") != dispatch_id:
                    continue
                if existing.get("job_id") != job_id:
                    raise SessionStoreError(
                        "persisted Sub-Agent result belongs to another Job"
                    )
                self._connection.execute("COMMIT")
                return int(row["message_id"])
            message_id = self._append_message_unlocked(
                session_id, "assistant", content, payload=payload
            )
            self._connection.execute("COMMIT")
            return message_id
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def import_jsonl(
        self,
        path: str | Path,
        *,
        project: str | None = None,
        entry_point: str = "jsonl-import",
    ) -> Session:
        """Import one legacy JSONL log into a new SQLite session."""
        if Path(path).suffix.lower() == ".uag":
            raise SessionStoreError(".uag requires encrypted portable import")
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        source_key = str(source.absolute())
        existing = self._execute(
            "SELECT session_id FROM legacy_imports WHERE source_path = ?",
            (source_key,),
        ).fetchone()
        if existing is not None:
            row = self.get_session(str(existing["session_id"]))
            return Session(
                row["session_id"],
                row.get("project"),
                row["entry_point"],
                row.get("project_key", ""),
                row.get("project_path"),
            )
        session = self.create_session(
            project=project or source.parent.name or "imported",
            project_path=source.parent,
            entry_point=entry_point,
        )
        try:
            # Importing one message per autocommit transaction is extremely
            # expensive for large JSONL logs and exposes a partially imported
            # session to other readers. Reserve the write lock before assigning
            # source sequence numbers, and keep the import atomic.
            self._connection.execute("BEGIN IMMEDIATE")
            with source.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(message, dict):
                        continue
                    role = message.get("role")
                    if role not in {"user", "assistant", "tool"}:
                        continue
                    content = str(message.get("content") or "")
                    self._append_message_unlocked(
                        session.session_id, str(role), content, payload=message
                    )
            self._execute(
                "INSERT INTO legacy_imports(source_path, session_id) VALUES (?, ?)",
                (source_key, session.session_id),
            )
            self._connection.execute("COMMIT")
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            try:
                self.delete_session(session.session_id)
            except Exception:
                pass
            raise
        return session

    @_db_locked
    def list_sessions(
        self,
        *,
        project: str | None = None,
        principal_id: str | None = None,
        limit: int | None = None,
        exclude_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List stored sessions, most recently used first.

        ``limit`` is applied in SQL rather than after fetching every session.
        This keeps the interactive ``:logs`` command fast on large histories.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if project is not None:
            clauses.append("s.project = ?")
            params.append(project)
        if principal_id is not None:
            clauses.append("s.principal_id = ?")
            params.append(principal_id)
        if exclude_session_id is not None:
            clauses.append("s.session_id <> ?")
            params.append(exclude_session_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ?"
            params.append(max(0, int(limit)))

        rows = self._execute(
            "SELECT s.session_id, s.project, s.project_path, s.entry_point, "
            "s.created_at, s.last_used_at, s.principal_id, s.room_id, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count, "
            "(SELECT content FROM messages m WHERE m.session_id = s.session_id AND m.role = 'user' ORDER BY message_id ASC LIMIT 1) AS first_message, "
            "(SELECT content FROM messages m WHERE m.session_id = s.session_id AND m.role = 'user' ORDER BY message_id DESC LIMIT 1) AS last_message, "
            "(SELECT summary FROM session_summaries ss WHERE ss.session_id = s.session_id) AS summary "
            "FROM sessions s"
            + where
            + " ORDER BY COALESCE(s.last_used_at, s.created_at) DESC, s.rowid DESC"
            + limit_sql,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]

    @_db_locked
    def delete_session(self, session_id: str) -> None:
        """Delete one session and all of its persisted data."""
        self._require_session(session_id)
        artifact_paths: list[str] = []
        try:
            self._connection.execute("BEGIN")
            has_artifacts = (
                self._connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'artifacts'"
                ).fetchone()
                is not None
            )
            if has_artifacts:
                artifact_paths = [
                    str(row["stored_path"])
                    for row in self._connection.execute(
                        "SELECT stored_path FROM artifacts WHERE session_id = ?",
                        (session_id,),
                    ).fetchall()
                ]
                self._execute(
                    "DELETE FROM artifacts WHERE session_id = ?", (session_id,)
                )
            self._execute(
                "DELETE FROM message_search WHERE session_id = ?", (session_id,)
            )
            self._execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            self._connection.execute("COMMIT")
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        _remove_global_artifact_dirs(artifact_paths)

    @_db_locked
    def vacuum(self) -> None:
        """Reclaim unused database pages after deletions."""
        try:
            self._connection.execute("VACUUM")
        except sqlite3.Error as exc:
            raise SessionStoreError(f"could not vacuum session store: {exc}") from exc

    @_db_locked
    def replace_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Replace a session's message history while preserving its identity."""
        self._require_session(session_id)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._execute(
                "UPDATE session_items SET availability = 'unavailable' "
                "WHERE session_id = ? AND item_kind = 'message' "
                "AND availability = 'available'",
                (session_id,),
            )
            self._execute(
                "DELETE FROM message_search WHERE session_id = ?", (session_id,)
            )
            self._execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "")
                if role not in {"system", "user", "assistant", "tool"}:
                    continue
                self._append_message_unlocked(
                    session_id,
                    role,
                    str(message.get("content") or ""),
                    payload=message,
                )
            self._connection.execute("COMMIT")
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        self._require_session(session_id)
        rows = self._execute(
            "SELECT message_id, session_id, role, content, payload_json, created_at "
            "FROM messages WHERE session_id = ? ORDER BY message_id",
            (session_id,),
        ).fetchall()
        messages: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            payload_json = item.pop("payload_json", None)
            if payload_json:
                try:
                    payload = json.loads(payload_json)
                except (TypeError, ValueError):
                    payload = None
                if isinstance(payload, dict):
                    payload.setdefault("role", item["role"])
                    messages.append(payload)
                    continue
            messages.append({"role": item["role"], "content": item["content"]})
        return messages

    @_db_locked
    def is_exact_indexed_message_available(self, ref: SourceRef) -> bool:
        """Check one exact indexed message without loading session history.

        The composite unique index on (session_id, item_kind, item_id)
        bounds this lookup independently of the session's message count.
        Missing/deleted, approximate or unavailable sources fail closed.
        """
        if not isinstance(ref, SourceRef) or ref.kind != "message":
            return False
        row = self._execute(
            "SELECT 1 FROM session_items AS si "
            "JOIN messages AS m ON m.message_id = CAST(si.item_id AS INTEGER) "
            "AND m.session_id = si.session_id "
            "AND CAST(m.message_id AS TEXT) = si.item_id "
            "WHERE si.session_id = ? AND si.item_kind = 'message' "
            "AND si.item_id = ? AND si.session_seq = ? "
            "AND si.ordering_quality = 'exact' "
            "AND si.availability = 'available' LIMIT 1",
            (ref.scope_id, ref.ref_id, ref.session_seq),
        ).fetchone()
        return row is not None

    @_db_locked
    def list_indexed_messages(self, session_id: str) -> list[dict[str, Any]]:
        """List available messages with their exact session-order references.

        Rows whose joined message payload is missing or whose ordering was only
        approximated are returned with that metadata intact so callers can
        decline provenance-sensitive work rather than guessing.
        """
        self._require_session(session_id)
        rows = self._execute(
            "SELECT si.session_seq, si.item_id AS ref_id, si.ordering_quality, "
            "si.availability, m.message_id, m.role, m.content, m.payload_json "
            "FROM session_items AS si LEFT JOIN messages AS m "
            "ON m.session_id = si.session_id "
            "AND CAST(m.message_id AS TEXT) = si.item_id "
            "WHERE si.session_id = ? AND si.item_kind = 'message' "
            "AND si.availability = 'available' ORDER BY si.session_seq",
            (session_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            payload_json = item.pop("payload_json", None)
            if payload_json:
                try:
                    payload = json.loads(payload_json)
                except (TypeError, ValueError):
                    payload = None
            else:
                payload = None
            item["payload"] = payload if isinstance(payload, dict) else None
            result.append(item)
        return result

    @_db_locked
    def record_response_state(
        self,
        session_id: str,
        *,
        provider: str,
        model: str,
        response_id: str,
        status: str,
    ) -> None:
        """Persist one completed Responses API state transition."""
        self._require_session(session_id)
        self._execute(
            "INSERT INTO response_states(session_id, provider, model, response_id, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, provider, model, response_id, status),
        )

    @_db_locked
    def latest_response_state(self, session_id: str) -> dict[str, Any] | None:
        self._require_session(session_id)
        row = self._execute(
            "SELECT provider, model, response_id, status, created_at "
            "FROM response_states WHERE session_id = ? "
            "ORDER BY state_id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return None if row is None else dict(row)

    @_db_locked
    def record_tool_context(
        self, session_id: str, *, tool_name: str, context: dict[str, Any]
    ) -> None:
        """Persist opaque, JSON-safe context owned by one tool."""
        self._require_session(session_id)
        try:
            context_json = _safe_json_dumps(context, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise SessionStoreError("tool context is not JSON serializable") from exc
        self._execute(
            "INSERT INTO tool_context_states(session_id, tool_name, context_json) "
            "VALUES (?, ?, ?)",
            (session_id, str(tool_name), context_json),
        )

    @_db_locked
    def latest_tool_context(self, session_id: str) -> dict[str, dict[str, Any]]:
        """Return the newest opaque context for each tool in a session."""
        self._require_session(session_id)
        rows = self._execute(
            "SELECT tool_name, context_json FROM tool_context_states "
            "WHERE session_id = ? ORDER BY context_id",
            (session_id,),
        ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                context = json.loads(row["context_json"])
            except (TypeError, ValueError):
                continue
            if isinstance(context, dict):
                result[str(row["tool_name"])] = context
        return result

    @_db_locked
    def record_tool_result(
        self,
        session_id: str,
        record: dict[str, Any],
        persistent_history: Any,
    ) -> None:
        """Persist one provider-neutral ToolResultRecord and its history view."""
        self._require_session(session_id)
        try:
            metadata_json = _safe_json_dumps(
                _sanitize_value(record.get("metadata") or {}),
                ensure_ascii=False,
                sort_keys=True,
            )
            persistent_json = _safe_json_dumps(
                _sanitize_value(sanitize_binary_payload(persistent_history)),
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise SessionStoreError("tool result is not JSON serializable") from exc
        result_id = str(record.get("result_id") or uuid.uuid4().hex)
        created_at = str(record.get("created_at") or _utc_now())
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            existing = self._execute(
                "SELECT session_id FROM tool_results WHERE result_id = ?",
                (result_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["session_id"]) != session_id:
                    raise SessionStoreError("tool result ID belongs to another session")
                self._record_session_item_unlocked(
                    session_id, "tool_result", result_id, ordering_quality="exact"
                )
                self._connection.execute("COMMIT")
                return
            self._execute(
                "INSERT INTO tool_results("
                "result_id, session_id, task_id, tool_name, result_class, size_bytes, "
                "summary, artifact_ref, importance, evictable, metadata_json, "
                "persistent_json, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result_id,
                    session_id,
                    str(record.get("task_id") or ""),
                    str(record.get("tool_name") or "tool"),
                    str(record.get("result_class") or "small"),
                    int(record.get("size_bytes") or 0),
                    _sanitize_text(str(record.get("summary") or "")),
                    _sanitize_text(str(record.get("artifact_ref") or "")),
                    str(record.get("importance") or "normal"),
                    1 if bool(record.get("evictable", True)) else 0,
                    metadata_json,
                    persistent_json,
                    created_at,
                ),
            )
            self._record_session_item_unlocked(
                session_id, "tool_result", result_id, ordering_quality="exact"
            )
            self._connection.execute("COMMIT")
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def list_tool_results(
        self, session_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return recent ToolResultRecords with decoded history projections."""
        self._require_session(session_id)
        safe_limit = max(1, min(int(limit), 10_000))
        rows = self._execute(
            "SELECT result_id, session_id, task_id, tool_name, result_class, "
            "size_bytes, summary, artifact_ref, importance, evictable, metadata_json, "
            "persistent_json, created_at FROM tool_results "
            "WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, safe_limit),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json"))
            except (TypeError, ValueError):
                item["metadata"] = {}
            try:
                item["persistent_history"] = json.loads(item.pop("persistent_json"))
            except (TypeError, ValueError):
                item["persistent_history"] = None
            item["evictable"] = bool(item["evictable"])
            results.append(item)
        return results

    @_db_locked
    def prune_tool_results(
        self,
        session_id: str,
        *,
        max_rows: int = 500,
        evictable_only: bool = True,
    ) -> int:
        """Delete oldest retained Tool Results within a session.

        By default only records marked ``evictable`` are removed. Artifact
        files are intentionally left untouched; their lifecycle is managed by
        the ArtifactManager cleanup policy.
        """
        self._require_session(session_id)
        safe_max_rows = max(0, min(int(max_rows), 100_000))
        if safe_max_rows == 0:
            return 0
        condition = "AND evictable = 1" if evictable_only else ""
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            rows = self._execute(
                "SELECT result_id FROM tool_results WHERE session_id = ? "
                f"{condition} ORDER BY created_at DESC LIMIT -1 OFFSET ?",
                (session_id, safe_max_rows),
            ).fetchall()
            if not rows:
                self._connection.execute("COMMIT")
                return 0
            ids = [str(row["result_id"]) for row in rows]
            placeholders = ",".join("?" for _ in ids)
            self._execute(
                "UPDATE session_items SET availability = 'unavailable' "
                "WHERE session_id = ? AND item_kind = 'tool_result' "
                f"AND item_id IN ({placeholders})",
                (session_id, *ids),
            )
            self._execute(
                f"DELETE FROM tool_results WHERE result_id IN ({placeholders})",
                tuple(ids),
            )
            self._connection.execute("COMMIT")
            return len(ids)
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def save_agent_state(
        self,
        session_id: str,
        state: dict[str, Any],
        *,
        expected_revision: int | None = None,
        updated_by_client: str | None = None,
    ) -> None:
        """Persist an AgentState update and advance its revision.

        ``expected_revision`` opts callers into optimistic concurrency. The
        reducer-owned structured namespace is preserved; this API cannot forge
        or erase that namespace. Omitting ``expected_revision`` is a legacy
        compatibility path and does not detect that ``state`` was built from a
        stale read; concurrent writers must pass the revision they observed.
        """
        self._require_session(session_id)
        if not isinstance(state, dict):
            raise SessionStoreError("agent state must be a JSON object")
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ValueError("expected_revision must be a non-negative integer")
        updated_at = str(state.get("updated_at") or _utc_now())
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            current = self._execute(
                "SELECT state_json, revision FROM agent_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            value = dict(state)
            value.pop("structured_compaction", None)
            if current is not None:
                try:
                    previous = json.loads(current["state_json"])
                except (TypeError, ValueError):
                    previous = None
                if isinstance(previous, dict) and "structured_compaction" in previous:
                    value["structured_compaction"] = previous["structured_compaction"]
            state_json = _safe_json_dumps(
                _sanitize_value(value), ensure_ascii=False, sort_keys=True
            )
            current_revision = int(current["revision"]) if current is not None else 0
            if expected_revision is not None and expected_revision != current_revision:
                raise SessionRevisionConflict(
                    f"expected AgentState revision {expected_revision}, found {current_revision}"
                )
            next_revision = current_revision + 1
            if current is None:
                self._execute(
                    "INSERT INTO agent_states(session_id, state_json, updated_at, "
                    "revision, updated_by_client) VALUES (?, ?, ?, ?, ?)",
                    (
                        session_id,
                        state_json,
                        updated_at,
                        next_revision,
                        updated_by_client,
                    ),
                )
            else:
                cursor = self._execute(
                    "UPDATE agent_states SET state_json = ?, updated_at = ?, revision = ?, "
                    "updated_by_client = ? WHERE session_id = ? AND revision = ?",
                    (
                        state_json,
                        updated_at,
                        next_revision,
                        updated_by_client,
                        session_id,
                        current_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise SessionRevisionConflict(
                        "AgentState changed while saving legacy state"
                    )
            self._connection.execute("COMMIT")
        except Exception as exc:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if isinstance(exc, SessionStoreError):
                raise
            if isinstance(exc, (TypeError, ValueError)):
                raise SessionStoreError("agent state is not JSON serializable") from exc
            raise

    @_db_locked
    def get_agent_state(self, session_id: str) -> dict[str, Any] | None:
        """Load the latest structured Agent State for a session."""
        self._require_session(session_id)
        row = self._execute(
            "SELECT state_json FROM agent_states WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            state = json.loads(row["state_json"])
        except (TypeError, ValueError) as exc:
            raise SessionStoreError("stored agent state is invalid JSON") from exc
        return state if isinstance(state, dict) else None

    @_db_locked
    def get_agent_state_revision(self, session_id: str) -> int:
        """Return the current revision (zero means no state row exists yet)."""
        self._require_session(session_id)
        row = self._execute(
            "SELECT revision FROM agent_states WHERE session_id = ?", (session_id,)
        ).fetchone()
        return int(row["revision"]) if row is not None else 0

    @_db_locked
    def get_agent_state_snapshot(
        self, session_id: str
    ) -> tuple[dict[str, Any] | None, int]:
        """Load AgentState and its revision together for optimistic updates."""
        self._require_session(session_id)
        row = self._execute(
            "SELECT state_json, revision FROM agent_states WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None, 0
        try:
            state = json.loads(row["state_json"])
        except (TypeError, ValueError) as exc:
            raise SessionStoreError("stored agent state is invalid JSON") from exc
        return (state if isinstance(state, dict) else None), int(row["revision"])

    @_db_locked
    def commit_sub_agent_receipt(
        self,
        record: HandoffRecord,
        *,
        source_session_id: str,
        expected_role: str,
        source_access_check: Callable[[SourceRef], bool],
        expected_job_id: str | None = None,
    ) -> dict[str, Any]:
        """Durably receive one unverified child report without applying state.

        Root-ID deduplication, Main revision validation and indexed source
        validation share one SQLite transaction. Replays of the exact record
        succeed even after Main's revision advances. This is a quarantined
        receipt, not a Goal update, decision, or completion signal.
        """
        if not isinstance(record, HandoffRecord):
            raise TypeError("record must be a HandoffRecord")
        if not callable(source_access_check):
            raise TypeError("source_access_check must be callable")
        if record.role != expected_role:
            raise SessionStoreError("receipt role does not match trusted host role")
        if expected_job_id is not None:
            if not isinstance(expected_job_id, str) or not expected_job_id.strip():
                raise SessionStoreError("invalid expected Sub-Agent Job ID")
        if (
            record.handoff_id != record.root_handoff_id
            or record.application_base_revision != record.receiving_base_revision
            or record.work_done
            or record.decisions
            or record.unresolved
            or record.recommended_next_steps
            or record.artifact_refs
            or record.source_checkpoint_id is not None
            or record.state_delta != ProvenancedDeterministicDelta()
            or len(record.findings) != 1
            or len(record.findings[0].source_refs) != 1
        ):
            raise SessionStoreError("receipt requires a single read-only child report")
        source = record.findings[0].source_refs[0]
        if (
            source.kind != "message"
            or source.scope_id != source_session_id
            or source.session_seq is None
            or not record.findings[0].text.startswith("Unverified Sub-Agent report (")
        ):
            raise SessionStoreError("receipt has no trusted child output source")
        serialized = record.to_json()
        if len(serialized.encode("utf-8")) > 128_000:
            raise SessionStoreError("compact return exceeds receipt size limit")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            parent = self.get_session(record.receiving_session_id)

            # After a committed receipt, replay can succeed without depending
            # on the mutable revision or availability of old source evidence.
            existing = self._execute(
                "SELECT receiving_session_id, source_session_id, record_json "
                "FROM sub_agent_receipts WHERE root_handoff_id = ?",
                (record.root_handoff_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["receiving_session_id"] != record.receiving_session_id
                    or existing["source_session_id"] != source_session_id
                    or existing["record_json"] != serialized
                ):
                    raise SessionStoreError(
                        "root handoff ID already has a different receipt"
                    )
                self._connection.execute("COMMIT")
                return {
                    "receiving_session_id": record.receiving_session_id,
                    "root_handoff_id": record.root_handoff_id,
                    "already_received": True,
                }

            child = self.get_session(source_session_id)
            if (
                child["entry_point"] != "sub-agent"
                or child["project_key"] != parent["project_key"]
                or child["principal_id"] != parent["principal_id"]
                or child["room_id"] != parent["room_id"]
            ):
                raise SessionStoreError("receipt child and receiver scope mismatch")

            current = self._execute(
                "SELECT revision FROM agent_states WHERE session_id = ?",
                (record.receiving_session_id,),
            ).fetchone()
            revision = int(current["revision"]) if current is not None else 0
            if revision != record.receiving_base_revision:
                raise SessionRevisionConflict(
                    "Sub-Agent return was produced for an older AgentState revision"
                )
            rows = self._execute(
                "SELECT m.message_id, m.role, m.content, m.payload_json, si.session_seq, "
                "si.ordering_quality, si.availability "
                "FROM messages m JOIN session_items si "
                "ON si.session_id = m.session_id "
                "AND si.item_kind = 'message' "
                "AND si.item_id = CAST(m.message_id AS TEXT) "
                "WHERE m.session_id = ?",
                (source_session_id,),
            ).fetchall()
            dispatches = []
            outputs = []
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"] or "null")
                except (ValueError, TypeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("dispatch_id") != record.root_handoff_id:
                    continue
                if row["role"] == "user":
                    if (
                        payload.get("receiving_session_id")
                        == record.receiving_session_id
                        and payload.get("receiving_base_revision")
                        == record.receiving_base_revision
                    ):
                        dispatches.append(row)
                elif row["role"] == "assistant":
                    outputs.append(row)
            if len(dispatches) != 1 or len(outputs) != 1:
                raise SessionStoreError("receipt dispatch or output is ambiguous")
            dispatch_row = dispatches[0]
            output = outputs[0]
            if (
                dispatch_row["ordering_quality"] != "exact"
                or dispatch_row["availability"] != "available"
                or output["ordering_quality"] != "exact"
                or output["availability"] != "available"
                or str(output["message_id"]) != source.ref_id
                or output["session_seq"] != source.session_seq
                or source_access_check(source) is not True
            ):
                raise SessionStoreError("receipt source unavailable or unauthorized")

            # A first receipt must be a faithful, unverified copy of
            # the indexed dispatch and child output. A public store caller
            # must not be able to reserve a root ID with invented contents.
            try:
                dispatch_payload = json.loads(dispatch_row["payload_json"] or "null")
                scope_snapshot = (
                    dispatch_payload.get("dispatch_scope")
                    if isinstance(dispatch_payload, dict)
                    else None
                )
                scoped = (
                    scope_snapshot
                    if scope_snapshot is not None
                    else json.loads(dispatch_row["content"])
                )
                output_payload = json.loads(output["payload_json"] or "null")
                report = (
                    output_payload.get("compact_report")
                    if isinstance(output_payload, dict)
                    else None
                )
                if report is None:
                    report = json.loads(output["content"])
            except (TypeError, ValueError) as exc:
                raise SessionStoreError(
                    "receipt lacks readable indexed dispatch or report"
                ) from exc
            if expected_job_id is not None and (
                not isinstance(output_payload, dict)
                or output_payload.get("job_id") != expected_job_id
            ):
                raise SessionStoreError(
                    "indexed Sub-Agent output belongs to another Job"
                )
            if not isinstance(scoped, dict) or not isinstance(report, dict):
                raise SessionStoreError("receipt dispatch or report has invalid shape")
            projected_goals = scoped.get("goals")
            if not isinstance(projected_goals, list) or any(
                not isinstance(goal, dict) or not isinstance(goal.get("goal_id"), str)
                for goal in projected_goals
            ):
                raise SessionStoreError("receipt dispatch Goals are invalid")
            if (
                scoped.get("kind") != "main_to_subagent"
                or scoped.get("receiving_session_id") != record.receiving_session_id
                or scoped.get("receiving_base_revision")
                != record.receiving_base_revision
                or scoped.get("objective") != record.objective
                or tuple(goal["goal_id"] for goal in projected_goals) != record.goal_ids
                or record.agent_id != f"sub-agent:{record.root_handoff_id}"
            ):
                raise SessionStoreError("receipt does not match indexed dispatch")
            report_status = report.get("status")
            report_summary = report.get("summary")
            if (
                not isinstance(report_status, str)
                or report_status
                not in {
                    "completed",
                    "error",
                    "blocked",
                    "incomplete",
                }
                or not isinstance(report_summary, str)
                or not report_summary.strip()
                or record.findings[0].text
                != (
                    f"Unverified Sub-Agent report "
                    f"({report_status}): {report_summary}"
                )
            ):
                raise SessionStoreError("receipt does not match indexed child output")

            self._execute(
                "INSERT INTO sub_agent_receipts("
                "root_handoff_id, receiving_session_id, source_session_id, "
                "base_revision, record_json, received_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.root_handoff_id,
                    record.receiving_session_id,
                    source_session_id,
                    record.receiving_base_revision,
                    serialized,
                    _utc_now(),
                ),
            )
            self._connection.execute("COMMIT")
            return {
                "receiving_session_id": record.receiving_session_id,
                "root_handoff_id": record.root_handoff_id,
                "already_received": False,
            }
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def get_compaction_record(self, operation_id: str) -> dict[str, Any] | None:
        """Load a committed compaction operation by its idempotency key."""
        row = self._execute(
            "SELECT checkpoint_id, operation_id, application_status, session_id, "
            "base_revision, result_revision, record_json FROM checkpoints "
            "WHERE operation_id = ?",
            (str(operation_id),),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            result["record"] = json.loads(result.pop("record_json"))
        except (TypeError, ValueError) as exc:
            raise SessionStoreError("stored CompactionRecord is invalid JSON") from exc
        return result

    @_db_locked
    def list_compaction_records(
        self,
        session_id: str,
        *,
        limit: int = 100,
        before_revision: int | None = None,
    ) -> list[dict[str, Any]]:
        """List applied checkpoints newest-first, with optional older-page access.

        Comparison-only records are excluded by construction. ``before_revision``
        pages older applied checkpoints without changing their immutable records.
        """
        self._require_session(session_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if before_revision is not None and (
            isinstance(before_revision, bool)
            or not isinstance(before_revision, int)
            or before_revision < 0
        ):
            raise ValueError("before_revision must be a non-negative integer")
        if limit == 0:
            return []

        sql = (
            "SELECT checkpoint_id, operation_id, application_status, session_id, "
            "base_revision, result_revision, source_start_seq, source_end_seq, "
            "created_at, record_json FROM checkpoints "
            "WHERE session_id = ? AND application_status = 'applied'"
        )
        params: list[Any] = [session_id]
        if before_revision is not None:
            sql += " AND result_revision < ?"
            params.append(before_revision)
        sql += " ORDER BY result_revision DESC, created_at DESC, checkpoint_id DESC LIMIT ?"
        params.append(limit)
        rows = self._execute(sql, tuple(params)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["record"] = json.loads(item.pop("record_json"))
            except (TypeError, ValueError) as exc:
                raise SessionStoreError(
                    "stored CompactionRecord is invalid JSON"
                ) from exc
            result.append(item)
        return result

    @_db_locked
    def commit_compaction_record(
        self,
        record: CompactionRecord,
        *,
        authorized_resolution_ids: tuple[str, ...] | list[str] = (),
    ) -> dict[str, Any]:
        """Atomically persist a checkpoint and, when applied, reduce AgentState.

        A retry must reuse the same operation_id. Any conflict or reducer error
        rolls back both the checkpoint and AgentState changes.
        """
        if not isinstance(record, CompactionRecord):
            raise TypeError("record must be a CompactionRecord")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._require_session(record.session_id)

            committed_record = record
            if record.application_status == "applied":
                next_revision = record.base_revision + 1
                if record.committed_revision not in (None, next_revision):
                    raise SessionStoreError("record committed_revision is inconsistent")
                if record.committed_revision is None:
                    from dataclasses import replace

                    committed_record = replace(record, committed_revision=next_revision)
            normalized_json = committed_record.to_json()

            # Check the idempotency key before inspecting mutable source/state:
            # after a successful commit either may have advanced or been pruned.
            existing = self._execute(
                "SELECT session_id, record_json FROM checkpoints WHERE operation_id = ?",
                (record.operation_id,),
            ).fetchone()
            if existing is not None:
                if existing["session_id"] != record.session_id:
                    raise SessionStoreError(
                        "operation_id is already used by another session"
                    )
                if existing["record_json"] != normalized_json:
                    raise SessionStoreError(
                        "operation_id retry payload differs from committed record"
                    )
                self._connection.execute("COMMIT")
                previous = self.get_compaction_record(record.operation_id)
                assert previous is not None
                previous["already_committed"] = True
                return previous

            if record.parent_checkpoint_id is not None:
                parent = self._execute(
                    "SELECT session_id FROM checkpoints WHERE checkpoint_id = ?",
                    (record.parent_checkpoint_id,),
                ).fetchone()
                if parent is None or parent["session_id"] != record.session_id:
                    raise SessionStoreError(
                        "parent_checkpoint_id must identify a checkpoint in this session"
                    )

            source_items = self.list_session_items(
                record.session_id,
                start_seq=record.source_start_seq,
                end_seq=record.source_end_seq,
                require_exact_order=True,
                require_available=True,
            )
            if len(source_items) != record.source_end_seq - record.source_start_seq + 1:
                raise SessionStoreError("source range is incomplete")

            source_kind_map = {
                "message": "message",
                "event": "runtime_event",
                "tool_call": "tool_call",
                "tool_result": "tool_result",
                "execution": "execution",
                "artifact": "artifact_link",
                "checkpoint": "checkpoint",
                "handoff": "handoff",
                "subagent": "subagent_result",
                "pending_operation": "runtime_event",
            }

            def validate_refs(value: Any) -> None:
                if isinstance(value, dict):
                    if {"kind", "ref_id", "scope_id", "session_seq"}.issubset(value):
                        sequence = value["session_seq"]
                        if sequence is not None:
                            if value["scope_id"] != record.session_id:
                                raise SessionStoreError(
                                    "session-sequenced SourceRef has a foreign scope"
                                )
                            source = self._execute(
                                "SELECT item_kind, item_id, ordering_quality, availability "
                                "FROM session_items WHERE session_id = ? AND session_seq = ?",
                                (record.session_id, sequence),
                            ).fetchone()
                            if (
                                source is None
                                or source["item_kind"]
                                != source_kind_map.get(value["kind"])
                                or source["item_id"] != value["ref_id"]
                                or source["availability"] != "available"
                                or source["ordering_quality"] == "legacy_approximate"
                            ):
                                raise SessionStoreError(
                                    "SourceRef does not resolve to an available indexed source"
                                )
                    for child in value.values():
                        validate_refs(child)
                elif isinstance(value, (list, tuple)):
                    for child in value:
                        validate_refs(child)

            validate_refs(record.to_dict())

            current_row = self._execute(
                "SELECT state_json, revision FROM agent_states WHERE session_id = ?",
                (record.session_id,),
            ).fetchone()
            current_revision = int(current_row["revision"]) if current_row else 0
            if (
                record.application_status == "applied"
                and record.base_revision != current_revision
            ):
                raise SessionRevisionConflict(
                    f"expected AgentState revision {record.base_revision}, found {current_revision}"
                )

            state_json = ""
            updated_at = ""
            if record.application_status == "applied":
                prior_state: dict[str, Any] | None = None
                if current_row is not None:
                    try:
                        prior_state = json.loads(current_row["state_json"])
                    except (TypeError, ValueError) as exc:
                        raise SessionStoreError(
                            "stored AgentState is invalid JSON"
                        ) from exc
                    if not isinstance(prior_state, dict):
                        raise SessionStoreError("stored AgentState is not an object")
                next_state = reduce_compaction_record(
                    prior_state,
                    committed_record,
                    authorized_resolution_ids=authorized_resolution_ids,
                )
                updated_at = _utc_now()
                next_state["updated_at"] = updated_at
                state_json = _safe_json_dumps(
                    _sanitize_value(next_state), ensure_ascii=False, sort_keys=True
                )
                result_revision: int | None = record.base_revision + 1
            else:
                if current_row is None:
                    raise SessionComparisonUnavailable(
                        "comparison_only unavailable: no saved AgentState snapshot "
                        f"is retained for base revision {record.base_revision}"
                    )
                if record.base_revision != current_revision:
                    raise SessionComparisonUnavailable(
                        "comparison_only unavailable: historical AgentState snapshot "
                        f"for base revision {record.base_revision} is not retained "
                        f"(current revision is {current_revision})"
                    )
                result_revision = None

            client_id = committed_record.client_instance_id
            self._execute(
                "INSERT INTO checkpoints(checkpoint_id, operation_id, application_status, "
                "actor_kind, actor_id, session_id, base_revision, result_revision, "
                "source_start_seq, source_end_seq, schema_version, parent_checkpoint_id, "
                "record_json, created_by_client, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    committed_record.record_id,
                    committed_record.operation_id,
                    committed_record.application_status,
                    committed_record.actor_kind,
                    committed_record.actor_id,
                    committed_record.session_id,
                    committed_record.base_revision,
                    result_revision,
                    committed_record.source_start_seq,
                    committed_record.source_end_seq,
                    committed_record.schema_version,
                    committed_record.parent_checkpoint_id,
                    normalized_json,
                    client_id,
                    committed_record.created_at,
                ),
            )
            self._record_session_item_unlocked(
                record.session_id, "checkpoint", committed_record.record_id
            )
            if record.application_status == "applied":
                if current_row is None:
                    if record.base_revision != 0:
                        raise SessionRevisionConflict(
                            "AgentState row is absent for nonzero base revision"
                        )
                    self._execute(
                        "INSERT INTO agent_states(session_id, state_json, updated_at, "
                        "revision, updated_by_client) VALUES (?, ?, ?, ?, ?)",
                        (
                            record.session_id,
                            state_json,
                            updated_at,
                            result_revision,
                            client_id,
                        ),
                    )
                else:
                    cursor = self._execute(
                        "UPDATE agent_states SET state_json = ?, updated_at = ?, revision = ?, "
                        "updated_by_client = ? WHERE session_id = ? AND revision = ?",
                        (
                            state_json,
                            updated_at,
                            result_revision,
                            client_id,
                            record.session_id,
                            record.base_revision,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise SessionRevisionConflict(
                            "AgentState revision changed during checkpoint commit"
                        )
            self._connection.execute("COMMIT")
            return {
                "checkpoint_id": committed_record.record_id,
                "operation_id": committed_record.operation_id,
                "application_status": committed_record.application_status,
                "session_id": committed_record.session_id,
                "base_revision": committed_record.base_revision,
                "result_revision": result_revision,
                "record": committed_record.to_dict(),
                "already_committed": False,
            }
        except Exception as exc:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if isinstance(exc, SessionStoreError):
                raise
            if isinstance(exc, (CompactionValidationError, CompactionReductionError)):
                raise SessionStoreError(
                    f"could not reduce CompactionRecord: {exc}"
                ) from exc
            if isinstance(exc, sqlite3.IntegrityError):
                raise SessionStoreError(f"checkpoint constraint failed: {exc}") from exc
            raise

    @_db_locked
    def get_tool_result(self, session_id: str, result_id: str) -> dict[str, Any] | None:
        """Return one persisted Tool Result by its stable result ID."""
        self._require_session(session_id)
        row = self._execute(
            "SELECT result_id, session_id, task_id, tool_name, result_class, "
            "size_bytes, summary, artifact_ref, importance, evictable, "
            "metadata_json, persistent_json, created_at FROM tool_results "
            "WHERE session_id = ? AND result_id = ?",
            (session_id, str(result_id)),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        for column, output in (
            ("metadata_json", "metadata"),
            ("persistent_json", "persistent_history"),
        ):
            try:
                item[output] = json.loads(item.pop(column))
            except (TypeError, ValueError):
                item[output] = {} if output == "metadata" else None
        item["evictable"] = bool(item["evictable"])
        return item

    @_db_locked
    def find_sessions_by_task_id(self, task_id: str) -> list[str]:
        """Return sessions that persisted results for one A2A Task ID."""
        value = str(task_id or "").strip()
        if not value:
            return []
        rows = self._execute(
            "SELECT DISTINCT session_id FROM tool_results WHERE task_id = ?",
            (value,),
        ).fetchall()
        return [str(row["session_id"]) for row in rows]

    @_db_locked
    def search_tool_results(
        self, session_id: str, query: str, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Find persisted Tool Results relevant to a query."""
        self._require_session(session_id)
        query = str(query or "").strip()
        if not query:
            return []
        safe_limit = max(1, min(int(limit), 100))
        tokens = [token.casefold() for token in re.findall(r"[\w-]+", query)]
        if not tokens:
            return []
        rows = self._execute(
            "SELECT result_id, session_id, task_id, tool_name, result_class, "
            "size_bytes, summary, artifact_ref, importance, evictable, "
            "metadata_json, persistent_json, created_at FROM tool_results "
            "WHERE session_id = ? ORDER BY created_at DESC LIMIT 1000",
            (session_id,),
        ).fetchall()
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        for row in rows:
            item = dict(row)
            for column, output in (
                ("metadata_json", "metadata"),
                ("persistent_json", "persistent_history"),
            ):
                try:
                    item[output] = json.loads(item.pop(column))
                except (TypeError, ValueError):
                    item[output] = {} if output == "metadata" else None
            item["evictable"] = bool(item["evictable"])
            fields = {
                "summary": str(item.get("summary") or "").casefold(),
                "tool_name": str(item.get("tool_name") or "").casefold(),
                "artifact_ref": str(item.get("artifact_ref") or "").casefold(),
                "content": json.dumps(
                    item.get("persistent_history"), ensure_ascii=False
                ).casefold(),
            }
            score = 0
            for token in tokens:
                if token in fields["summary"]:
                    score += 8
                if token in fields["tool_name"]:
                    score += 5
                if token in fields["artifact_ref"]:
                    score += 3
                if token in fields["content"]:
                    score += 1
            if score:
                ranked.append((score, str(item.get("created_at") or ""), item))
        ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
        return [item for _, _, item in ranked[:safe_limit]]

    @_db_locked
    def record_policy_decision(
        self,
        session_id: str,
        *,
        tool_name: str,
        decision: str,
        args: dict[str, Any] | None = None,
        reason: str = "",
        tool_call_id: str | None = None,
    ) -> int:
        """Persist a redacted authorization decision for one tool call."""
        if decision not in {"allow", "confirm", "deny"}:
            raise ValueError(f"invalid policy decision: {decision}")
        self._require_session(session_id)
        try:
            safe_args_json = _safe_json_dumps(
                mask_args(_sanitize_value(args or {})),
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise SessionStoreError(
                "policy decision arguments are not JSON serializable"
            ) from exc
        cursor = self._execute(
            "INSERT INTO policy_decisions "
            "(session_id, tool_call_id, tool_name, decision, args_json, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                tool_call_id,
                str(tool_name),
                decision,
                safe_args_json,
                _sanitize_text(redact_sensitive(_sanitize_text(str(reason or "")))),
            ),
        )
        return int(cursor.lastrowid)

    @_db_locked
    def list_policy_decisions(self, session_id: str) -> list[dict[str, Any]]:
        self._require_session(session_id)
        rows = self._execute(
            "SELECT decision_id, session_id, tool_call_id, tool_name, decision, "
            "args_json, reason, created_at FROM policy_decisions "
            "WHERE session_id = ? ORDER BY decision_id",
            (session_id,),
        ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["args"] = json.loads(item.pop("args_json"))
            except (TypeError, ValueError):
                item["args"] = {}
                item.pop("args_json", None)
            output.append(item)
        return output

    @_db_locked
    def record_context_decisions(
        self,
        session_id: str,
        decisions: list[dict[str, Any]],
    ) -> int:
        """Persist redacted Active Context decisions for one LLM turn."""
        self._require_session(session_id)
        count = 0
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            try:
                importance = (
                    float(decision["importance"])
                    if decision.get("importance") is not None
                    else None
                )
            except (TypeError, ValueError):
                importance = None
            self._execute(
                "INSERT INTO context_decisions "
                "(session_id, item_id, source, section, action, reason, importance, "
                "original_chars, projected_chars, reference) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    _sanitize_text(str(decision.get("item_id") or "")),
                    _sanitize_text(str(decision.get("source") or "")),
                    _sanitize_text(str(decision.get("section") or "")),
                    _sanitize_text(str(decision.get("action") or "")),
                    _sanitize_text(redact_sensitive(str(decision.get("reason") or ""))),
                    importance,
                    decision.get("original_chars"),
                    decision.get("projected_chars"),
                    _sanitize_text(
                        redact_sensitive(str(decision.get("reference") or ""))
                    )
                    or None,
                ),
            )
            count += 1
        return count

    @_db_locked
    def list_context_decisions(
        self, session_id: str, *, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Return persisted Active Context decisions, oldest first."""
        self._require_session(session_id)
        safe_limit = max(0, min(int(limit), 10_000))
        rows = self._execute(
            "SELECT decision_id, session_id, item_id, source, section, action, "
            "reason, importance, original_chars, projected_chars, reference, "
            "created_at FROM context_decisions "
            "WHERE session_id = ? ORDER BY decision_id LIMIT ?",
            (session_id, safe_limit),
        ).fetchall()
        return [dict(row) for row in rows]

    @_db_locked
    def record_tool_call(
        self,
        session_id: str,
        *,
        tool_name: str,
        args: dict[str, Any],
        result: str,
        status: str,
        call_id: str | None = None,
    ) -> str:
        if status not in {"success", "failed", "timeout", "cancelled"}:
            raise ValueError(f"invalid tool-call status: {status}")
        self._require_session(session_id)
        call_id = call_id or uuid.uuid4().hex
        try:
            safe_args = mask_args(_sanitize_value(args))
            args_json = _safe_json_dumps(safe_args, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise SessionStoreError(
                "tool-call arguments are not JSON serializable"
            ) from exc
        safe_result = _sanitize_text(
            redact_sensitive(
                _sanitize_text(result if isinstance(result, str) else str(result or ""))
            )
        )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            existing = self._execute(
                "SELECT call_id, session_id FROM tool_calls WHERE call_id = ?",
                (call_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["session_id"]) != session_id:
                    raise SessionStoreError("tool call ID belongs to another session")
                self._record_session_item_unlocked(
                    session_id,
                    "tool_call",
                    call_id,
                    ordering_quality="legacy_approximate",
                )
                self._connection.execute("COMMIT")
                return str(existing["call_id"])
            self._execute(
                "INSERT INTO tool_calls(call_id, session_id, tool_name, args_json, result, status) VALUES (?, ?, ?, ?, ?, ?)",
                (call_id, session_id, tool_name, args_json, safe_result, status),
            )
            self._record_session_item_unlocked(
                session_id,
                "tool_call",
                call_id,
                ordering_quality="legacy_approximate",
            )
            self._connection.execute("COMMIT")
            return call_id
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def list_tool_calls(self, session_id: str) -> list[dict[str, Any]]:
        self._require_session(session_id)
        rows = self._execute(
            "SELECT call_id, session_id, tool_name, args_json, result, status, created_at FROM tool_calls WHERE session_id = ? ORDER BY created_at, rowid",
            (session_id,),
        ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["args"] = json.loads(item.pop("args_json"))
            output.append(item)
        return output

    @_db_locked
    def save_session_summary(self, session_id: str, summary: str) -> None:
        self._require_session(session_id)
        summary = _sanitize_text(
            redact_sensitive(
                _sanitize_text(
                    summary if isinstance(summary, str) else str(summary or "")
                )
            )
        ).strip()
        if not summary:
            raise ValueError("summary is empty")
        self._execute(
            "INSERT INTO session_summaries(session_id, summary) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, created_at=CURRENT_TIMESTAMP",
            (session_id, summary),
        )

    @_db_locked
    def get_session_summary(self, session_id: str) -> str | None:
        self._require_session(session_id)
        row = self._execute(
            "SELECT summary FROM session_summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return None if row is None else str(row["summary"])

    @_db_locked
    def summary_is_stale(self, session_id: str) -> bool:
        """Return True when the session gained messages after its summary.

        A session that already has a summary still needs re-summarization
        when the conversation continued after the summary was created (for
        example after ``:load`` + more turns, or mid-session summarize).
        """
        self._require_session(session_id)
        row = self._execute(
            "SELECT "
            "(SELECT MAX(created_at) FROM messages WHERE session_id = ?) AS last_message_at, "
            "(SELECT created_at FROM session_summaries WHERE session_id = ?) AS summary_at",
            (session_id, session_id),
        ).fetchone()
        if row is None:
            return False
        last_message_at = row["last_message_at"]
        summary_at = row["summary_at"]
        if not last_message_at or not summary_at:
            return False
        return str(last_message_at) > str(summary_at)

    @_db_locked
    def list_memory_candidates(self, session_id: str) -> list[str]:
        """Return explicitly marked candidates without persisting them."""
        self._require_session(session_id)
        rows = self._execute(
            "SELECT content FROM messages WHERE session_id = ? AND role = 'user' ORDER BY message_id",
            (session_id,),
        ).fetchall()
        candidates = []
        for row in rows:
            content = str(row["content"])
            marker = next(
                (
                    prefix
                    for prefix in ("remember:", "記憶:")
                    if content.lower().startswith(prefix)
                ),
                None,
            )
            if marker:
                value = content[len(marker) :].strip()
                if value:
                    candidates.append(value)
        return candidates

    @_db_locked
    def search(
        self, query: str, *, project: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        query_like = f"%{query}%"
        # MATCH accepts a query language. Quote user input so punctuation
        # (for example ``new-1``) cannot become an FTS operator or column
        # reference and turn an ordinary search into an OperationalError.
        fts_query = '"' + query.replace('"', '""') + '"'
        parameters: list[Any] = [fts_query, query_like, query_like, max(1, limit)]
        project_clause = ""
        if project is not None:
            project_clause = " AND s.project = ?"
            parameters.insert(-1, project)
        rows = self._execute(
            """
            SELECT m.session_id, s.project, s.entry_point, m.message_id,
                   m.role, m.content, m.created_at
            FROM messages m
            JOIN sessions s ON s.session_id = m.session_id
            WHERE (
                m.message_id IN (
                    SELECT message_id FROM message_search WHERE message_search MATCH ?
                ) OR m.content LIKE ? OR m.payload_json LIKE ?
            )
            """ + project_clause + " ORDER BY m.message_id LIMIT ?",
            tuple(parameters),
        ).fetchall()
        return [dict(row) for row in rows]


def attach_opt_in_session_store(
    core: Any, *, project_path: str | Path, entry_point: str
) -> tuple[SessionStore | None, str | None]:
    """Attach the opt-in store to any UAG entry point using its log callback."""
    store = SessionStore.from_environment()
    if store is None:
        return None, None
    session = store.create_session(
        project=project_id_from_path(project_path),
        project_path=project_path,
        entry_point=entry_point,
    )
    original_log_message = core.log_message
    core._session_store_original_log_message = original_log_message
    # The CLI can switch the loaded conversation with :load. Keep the active
    # persistence target on core so the callback does not permanently capture
    # the session created at startup.
    core._session_store_active_id = session.session_id
    from .agent_state import AgentState, AgentStateManager

    persisted_agent_state = store.get_agent_state(session.session_id)
    agent_state_manager = AgentStateManager(
        AgentState.from_dict(persisted_agent_state)
        if persisted_agent_state
        else AgentState()
    )
    pending_tool_calls: dict[str, tuple[str, dict[str, Any]]] = {}

    jsonl_enabled = (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() != "sqlite"
    )

    def log_message(message: dict[str, Any]) -> None:
        try:
            from .observability.content_runtime import capture_logged_message

            capture_logged_message(message)
        except Exception:
            pass
        if jsonl_enabled:
            original_log_message(message)
        if getattr(core, "_session_store_write_disabled", False):
            return
        role = message.get("role") if isinstance(message, dict) else None
        if role not in {"system", "user", "assistant", "tool"}:
            return
        content = str(message.get("content") or "")
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        try:
            store.append_message(
                active_session_id,
                str(role),
                content,
                payload=message if isinstance(message, dict) else None,
            )
        except SessionStoreError as exc:
            if "locked" not in str(exc).lower():
                raise
            # Session persistence is auxiliary; a competing process must not
            # terminate the interactive LLM operation. Disable only the
            # SQLite callback for the remainder of this entry point.
            core._session_store_write_disabled = True
            return
        if role == "assistant":
            for call in message.get("tool_calls") or []:
                if isinstance(call, dict):
                    call_id, name, args = normalize_tool_call(call)
                    if call_id:
                        pending_tool_calls[call_id] = (name, args)
        elif role == "tool" and message.get("tool_call_id"):
            call_id = str(message["tool_call_id"])
            name, args = pending_tool_calls.pop(
                call_id, (str(message.get("name") or "tool"), {})
            )
            status = "failed" if "[tool runtime error]" in content else "success"
            store.record_tool_call(
                active_session_id,
                tool_name=name,
                args=args,
                result=content,
                status=status,
                call_id=call_id,
            )

    def record_tool_result(record: dict[str, Any], persistent_history: Any) -> None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        store.record_tool_result(
            active_session_id,
            record,
            persistent_history,
        )
        raw_max_rows = os.environ.get("UAGENT_TOOL_RESULT_MAX_ROWS", "500")
        try:
            max_rows = int(raw_max_rows)
        except (TypeError, ValueError):
            max_rows = 500
        if max_rows > 0:
            store.prune_tool_results(active_session_id, max_rows=max_rows)

    def prune_tool_results(max_rows: int = 500, evictable_only: bool = True) -> int:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        return store.prune_tool_results(
            active_session_id,
            max_rows=max_rows,
            evictable_only=evictable_only,
        )

    def save_agent_state(
        state: dict[str, Any], *, expected_revision: int | None = None
    ) -> None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        store.save_agent_state(
            active_session_id, state, expected_revision=expected_revision
        )

    def complete_agent_step(step: str, next_action: str = "") -> dict[str, Any]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        persisted, expected_revision = store.get_agent_state_snapshot(active_session_id)
        manager = AgentStateManager(
            AgentState.from_dict(persisted) if persisted else AgentState()
        )
        state = manager.mark_step_complete(step, next_action=next_action)
        core.agent_state_manager = manager
        store.save_agent_state(
            active_session_id, state.to_dict(), expected_revision=expected_revision
        )
        return state.to_dict()

    def update_agent_state(**changes: Any) -> dict[str, Any]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        persisted, expected_revision = store.get_agent_state_snapshot(active_session_id)
        manager = AgentStateManager(
            AgentState.from_dict(persisted) if persisted else AgentState()
        )
        state = manager.update(**changes)
        core.agent_state_manager = manager
        store.save_agent_state(
            active_session_id, state.to_dict(), expected_revision=expected_revision
        )
        return state.to_dict()

    def get_agent_state() -> dict[str, Any] | None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        state = store.get_agent_state(active_session_id)
        core.agent_state_manager = AgentStateManager(
            AgentState.from_dict(state) if state else AgentState()
        )
        return state

    def get_tool_result(result_id: str) -> dict[str, Any] | None:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        return store.get_tool_result(active_session_id, result_id)

    def artifact_cleanup(execute: bool = False) -> dict[str, Any]:
        """Return or execute cleanup for the active Session."""
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        from .artifact_manager import ArtifactManager

        workdir = Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        manager = ArtifactManager(workdir, store=store)
        try:
            records = store.list_tool_results(active_session_id, limit=10_000)
            referenced = {
                str(record.get("artifact_ref") or "").removeprefix("artifact://")
                for record in records
                if record.get("artifact_ref")
            }
            return manager.cleanup(
                referenced_ids={item for item in referenced if item},
                session_id=active_session_id,
                execute=execute,
            )
        finally:
            manager.close()

    def artifact_cleanup_report() -> dict[str, Any]:
        """Return a dry-run cleanup report for the active Session."""
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        from .artifact_manager import ArtifactManager

        workdir = Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        manager = ArtifactManager(workdir, store=store)
        try:
            records = store.list_tool_results(active_session_id, limit=10_000)
            referenced = {
                str(record.get("artifact_ref") or "").removeprefix("artifact://")
                for record in records
                if record.get("artifact_ref")
            }
            return manager.cleanup_report(
                referenced_ids={item for item in referenced if item},
                session_id=active_session_id,
            )
        finally:
            manager.close()

    def read_artifact_preview(reference: str, max_chars: int = 4000) -> str:
        """Read a bounded textual Artifact preview owned by the active session."""
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        artifact_id = str(reference or "").strip().removeprefix("artifact://")
        if not re.fullmatch(r"[0-9a-f]{32}", artifact_id):
            return ""
        from .artifact_manager import ArtifactManager

        workdir = Path(os.environ.get("UAGENT_WORKDIR") or os.getcwd())
        manager = ArtifactManager(workdir, store=store)
        try:
            item = manager.get(artifact_id)
            if item.session_id != active_session_id:
                return ""
            media_type = (item.media_type or "").lower()
            if not (media_type.startswith("text/") or "json" in media_type):
                return ""
            return manager.open(artifact_id).read_text(
                encoding="utf-8", errors="replace"
            )[: max(0, int(max_chars))]
        except Exception:
            return ""
        finally:
            manager.close()

    def search_tool_results(query: str, limit: int = 10) -> list[dict[str, Any]]:
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        return store.search_tool_results(active_session_id, query, limit=limit)

    def retrieve_tool_context(
        query: str, limit: int = 10, max_chars: int = 12_000
    ) -> str:
        from .tool_result_manager import ContextResultManager

        records = search_tool_results(query, limit=limit)
        for record in records:
            artifact_ref = str(record.get("artifact_ref") or "")
            if artifact_ref:
                preview = read_artifact_preview(artifact_ref, max_chars=2000)
                if preview:
                    record["artifact_preview"] = preview
        return ContextResultManager().format_retrieved_context(
            records, max_chars=max_chars
        )

    core.log_message = log_message
    core.record_tool_result = record_tool_result
    core.prune_tool_results = prune_tool_results
    core.agent_state_manager = agent_state_manager
    core.save_agent_state = save_agent_state
    core.update_agent_state = update_agent_state
    core.complete_agent_step = complete_agent_step
    core.get_agent_state = get_agent_state
    core.get_tool_result = get_tool_result
    core.artifact_cleanup_report = artifact_cleanup_report
    core.artifact_cleanup = artifact_cleanup
    core.read_artifact_preview = read_artifact_preview
    core.search_tool_results = search_tool_results
    core.retrieve_tool_context = retrieve_tool_context
    core.session_store = store
    try:
        from ..tools.context import get_callbacks

        callbacks = get_callbacks()
        callbacks.session_store = store
        callbacks.session_id = session.session_id
    except Exception:
        pass
    atexit.register(detach_opt_in_session_store, core)
    core.session_id = session.session_id
    return store, session.session_id


def detach_opt_in_session_store(core: Any) -> None:
    """Close and detach a store previously attached to an entry point."""
    store = getattr(core, "session_store", None)
    try:
        if store is not None:
            store.close()
    finally:
        original = getattr(core, "_session_store_original_log_message", None)
        if original is not None:
            core.log_message = original
        # Attach mutates the process-wide tool callback object. Clear only the
        # state belonging to this store so a later entry point cannot retain a
        # closed SQLite connection or stale session ID.
        try:
            from ..tools.context import get_callbacks

            callbacks = get_callbacks()
            if getattr(callbacks, "session_store", None) is store:
                callbacks.session_store = None
                callbacks.session_id = None
        except Exception:
            pass
        for name in (
            "session_store",
            "session_id",
            "record_tool_result",
            "prune_tool_results",
            "agent_state_manager",
            "save_agent_state",
            "update_agent_state",
            "complete_agent_step",
            "get_agent_state",
            "get_tool_result",
            "artifact_cleanup_report",
            "artifact_cleanup",
            "read_artifact_preview",
            "search_tool_results",
            "retrieve_tool_context",
            "_session_store_active_id",
            "_session_store_original_log_message",
        ):
            try:
                delattr(core, name)
            except AttributeError:
                pass


__all__ = [
    "Session",
    "SessionStore",
    "SessionStoreError",
    "attach_opt_in_session_store",
    "detach_opt_in_session_store",
    "normalize_tool_call",
    "project_id_from_path",
    "redact_sensitive",
    "_sanitize_text",
    "_sanitize_value",
    "_safe_json_dumps",
]
