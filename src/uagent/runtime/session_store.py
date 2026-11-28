"""SQLite-backed session, message, and tool-call persistence."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ..i18n import _
from ..utils.paths import get_state_dir
from ..utils.secret_mask import mask_args
from .compaction_record import SourceRef
from .tool_result_persistence import (
    sanitize_message_for_history,
)

from .session_store_common import (  # noqa: F401  (re-exported)
    Session,
    SessionComparisonUnavailable,
    SessionRevisionConflict,
    SessionStoreError,
    _SCHEMA_VERSION,
    _SESSION_ITEM_KINDS,
    _SESSION_ITEM_ORDERING_QUALITIES,
    _TOOL_IDENTITY_DDL,
    _TOOL_IDENTITY_INDEX_DDL,
    _TOOL_IDENTITY_REBUILD_SPECS,
    _db_locked,
    _migrate_legacy_session_store,
    _remove_global_artifact_dirs,
    _safe_json_dumps,
    _sanitize_text,
    _sanitize_value,
    normalize_tool_call,
    project_id_from_path,
    redact_sensitive,
)
from .session_store_tools import _ToolRecordsMixin
from .session_store_agent_state import _AgentStateMixin
from .session_store_receipts import _SubAgentReceiptMixin
from .session_store_compaction import _CompactionRecordMixin
from .session_store_index import _SearchIndexMixin

_SQLITE_LOCK_RETRIES = 3
_SQLITE_LOCK_RETRY_DELAY = 0.25


def normalize_workdir_key(path: Any) -> str:
    """Return the comparison key for a workdir path (``""`` when unknown).

    The key is the absolute, normalized path; ``os.path.normcase`` folds
    case on Windows only, matching each platform's path semantics.
    """

    text = str(path or "").strip()
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(os.path.normpath(text)))


def cwd_path_from_content(content: Any) -> str:
    """Extract the path from a ``[CWD]`` system message, or ``""``."""

    if not isinstance(content, str) or not content.startswith("[CWD] "):
        return ""
    try:
        obj = json.loads(content[len("[CWD] ") :].strip())
    except Exception:
        return ""
    if isinstance(obj, dict):
        path = obj.get("path")
        if isinstance(path, str) and path.strip():
            return path
    return ""


def final_workdir_from_messages(messages: Any, project_path: Any = None) -> str:
    """Return a session's final workdir: its last ``[CWD]`` path.

    Falls back to the recorded project path when no marker exists, and
    to ``""`` (unknown) when neither is recorded — never a guess.
    """

    for message in reversed(list(messages or [])):
        if isinstance(message, dict) and message.get("role") == "system":
            path = cwd_path_from_content(message.get("content"))
            if path:
                return path
    return str(project_path or "")


class SessionStore(
    _ToolRecordsMixin,
    _AgentStateMixin,
    _SubAgentReceiptMixin,
    _CompactionRecordMixin,
    _SearchIndexMixin,
):
    """Small repository for durable session data.

    The class owns one SQLite connection per instance. It intentionally stores
    redacted text only and uses parameterized SQL for all user-controlled data.
    """

    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        self._memory_notices: list[str] = []
        self._terms_lock = threading.Lock()
        self._terms_thread_active = False
        self._terms_last_finished = 0.0
        wait_ms = max(int(busy_timeout_ms), 0)
        try:
            # Multiple CLI/Web/A2A processes may share one store. WAL lets
            # readers proceed while a writer commits, and the longer busy
            # timeout avoids failing on normal short-lived writer contention.
            self._connection = sqlite3.connect(
                self.path,
                timeout=wait_ms / 1000.0,
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute(f"PRAGMA busy_timeout = {wait_ms}")
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
                    final_workdir TEXT,
                    final_workdir_key TEXT,
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
                CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
                    content, session_id UNINDEXED, message_id UNINDEXED
                );
                CREATE TABLE IF NOT EXISTS message_terms (
                    message_id INTEGER PRIMARY KEY
                        REFERENCES messages(message_id) ON DELETE CASCADE,
                    terms TEXT NOT NULL
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
                CREATE TABLE IF NOT EXISTS sub_agent_review_registry_owners (
                    session_id TEXT PRIMARY KEY
                        REFERENCES sessions(session_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sub_agent_receipt_reviews (
                    root_handoff_id TEXT PRIMARY KEY
                        REFERENCES sub_agent_receipts(root_handoff_id)
                        ON DELETE CASCADE,
                    receiving_session_id TEXT NOT NULL
                        REFERENCES sessions(session_id) ON DELETE CASCADE,
                    reviewer_id TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK(outcome IN ('supported', 'rejected')),
                    evidence_refs_json TEXT NOT NULL,
                    base_revision INTEGER NOT NULL CHECK(base_revision >= 0),
                    reviewed_at TEXT NOT NULL
                );
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
                CREATE INDEX IF NOT EXISTS idx_messages_session_role_id
                    ON messages(session_id, role, message_id);
                CREATE INDEX IF NOT EXISTS idx_policy_decisions_session_id
                    ON policy_decisions(session_id, decision_id);
                CREATE INDEX IF NOT EXISTS idx_context_decisions_session_id
                    ON context_decisions(session_id, decision_id);
                """)
            # Tool identity tables live outside the block above so the versioned
            # migration can rebuild them from the same definitions.
            for statement in _TOOL_IDENTITY_DDL:
                self._connection.execute(statement)
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
            if "final_workdir" not in columns:
                self._connection.execute(
                    "ALTER TABLE sessions ADD COLUMN final_workdir TEXT"
                )
            if "final_workdir_key" not in columns:
                self._connection.execute(
                    "ALTER TABLE sessions ADD COLUMN final_workdir_key TEXT"
                )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_final_workdir_key "
                "ON sessions(final_workdir_key)"
            )
            self._backfill_final_workdir()
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
            self._migrate_schema()
            self._backfill_session_items()
        except sqlite3.Error as exc:
            raise SessionStoreError(
                f"could not initialize session store: {exc}"
            ) from exc

    def _migrate_schema(self) -> None:
        """Apply structural migrations and record the resulting version.

        Runs on every open so a store written by an older build is upgraded in
        place. Each step must be idempotent because the version is only a hint
        for stores that predate it.
        """
        row = self._connection.execute("PRAGMA user_version").fetchone()
        version = int(row[0] or 0)
        if version >= _SCHEMA_VERSION:
            return
        if version < 1:
            self._migrate_tool_identity_to_session_scope()
        self._connection.execute(f"PRAGMA user_version = {int(_SCHEMA_VERSION)}")

    def _has_session_scoped_primary_key(self, table: str, column: str) -> bool:
        """Return True when ``table`` already keys on (session_id, column)."""
        primary = {
            str(row["name"]): int(row["pk"] or 0)
            for row in self._connection.execute(f"PRAGMA table_info({table})")
        }
        return primary.get("session_id", 0) > 0 and primary.get(column, 0) > 0

    def _rebuild_identity_table(
        self,
        table: str,
        create_sql: str,
        columns: tuple[str, ...],
    ) -> None:
        """Rebuild ``table`` with the session-scoped key in ``create_sql``."""
        legacy = f"_{table}_legacy_identity"
        column_list = ", ".join(columns)
        self._connection.execute(f"DROP TABLE IF EXISTS {legacy}")
        self._connection.execute(f"ALTER TABLE {table} RENAME TO {legacy}")
        self._connection.execute(create_sql)
        self._connection.execute(
            f"INSERT INTO {table}({column_list}) " f"SELECT {column_list} FROM {legacy}"
        )
        self._connection.execute(f"DROP TABLE {legacy}")

    def _migrate_tool_identity_to_session_scope(self) -> None:
        """Rebuild tool identity tables with session-scoped primary keys.

        Provider- and import-supplied call/result IDs are only unique inside a
        conversation, so a store-wide key made any second session that reused
        an ID fail with "belongs to another session" and abort its LLM round.
        """
        pending = [
            spec
            for spec in _TOOL_IDENTITY_REBUILD_SPECS
            if not self._has_session_scoped_primary_key(spec[0], spec[1])
        ]
        if not pending:
            return
        for attempt in range(_SQLITE_LOCK_RETRIES + 1):
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                try:
                    for table, _column, index_name, _sql, _columns in pending:
                        # The renamed table keeps its old index, so drop it now
                        # and recreate it over the rebuilt table below.
                        self._connection.execute(f"DROP INDEX IF EXISTS {index_name}")
                    for table, _column, _index, create_sql, columns in pending:
                        self._rebuild_identity_table(table, create_sql, columns)
                    for statement in _TOOL_IDENTITY_INDEX_DDL:
                        self._connection.execute(statement)
                    self._connection.execute("COMMIT")
                except Exception:
                    try:
                        self._connection.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                    raise
                return
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < _SQLITE_LOCK_RETRIES:
                    time.sleep(_SQLITE_LOCK_RETRY_DELAY * (2**attempt))
                    continue
                raise

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

    def _backfill_final_workdir(self) -> None:
        """Fill final_workdir for sessions recorded before it existed.

        Uses each session's last ``[CWD]`` marker, falling back to its
        project path. Sessions with neither stay unknown (empty key) —
        the value is never guessed.
        """

        rows = self._connection.execute(
            "SELECT session_id, project_path FROM sessions "
            "WHERE final_workdir_key IS NULL"
        ).fetchall()
        for row in rows:
            session_id = row["session_id"]
            marker = self._connection.execute(
                "SELECT content FROM messages WHERE session_id = ? "
                "AND role = 'system' AND content LIKE '[CWD] %' "
                "ORDER BY message_id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            path = cwd_path_from_content(marker["content"]) if marker else ""
            if not path:
                path = str(row["project_path"] or "")
            self._connection.execute(
                "UPDATE sessions SET final_workdir = ?, final_workdir_key = ? "
                "WHERE session_id = ?",
                (path or None, normalize_workdir_key(path), session_id),
            )

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
            "INSERT INTO sessions(session_id, project, project_key, project_path, final_workdir, final_workdir_key, entry_point) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                project,
                project_key,
                path_value,
                path_value,
                normalize_workdir_key(path_value),
                entry_point,
            ),
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
        safe_content = _sanitize_text(
            redact_sensitive(content, strip_binary=role == "tool")
        )
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
            except Exception:
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
        self._index_message_terms_unlocked(message_id, safe_content)
        self._record_session_item_unlocked(
            session_id, "message", str(message_id), ordering_quality="exact"
        )
        if role == "system":
            cwd_path = cwd_path_from_content(safe_content)
            if cwd_path:
                self._execute(
                    "UPDATE sessions SET final_workdir = ?, final_workdir_key = ? "
                    "WHERE session_id = ?",
                    (cwd_path, normalize_workdir_key(cwd_path), session_id),
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
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        self._save_memory_marker(content, role)
        return message_id

    def _save_memory_marker(
        self,
        content: str,
        role: str,
        *,
        allow_scoped: bool = True,
        replay: bool = False,
    ) -> None:
        """Save a ``remember:``/``記憶：`` marked user note immediately.

        Runs after the message transaction commits and never raises: the
        marker fallback must not break message logging. Successful saves
        queue a one-line notice for the UI (see drain_memory_notices).
        ``allow_scoped=False`` and ``replay=True`` are used by history
        rewrites: scoped saves must not re-fire there, and local replays
        stay behind the forget boundary (see replace_messages).
        """
        if role != "user":
            return
        try:
            from .memory_marker import extract_memory_marker, save_memory_marker

            note = extract_memory_marker(content)
            if note is None:
                return
            result = save_memory_marker(
                content, allow_scoped=allow_scoped, replay=replay
            )
            if result and result.get("saved"):
                self._memory_notices.append(
                    _("[memory] saved from marker: %(note)s")
                    % {"note": " ".join(note.split())[:80]}
                )
        except Exception:
            pass

    def drain_memory_notices(self) -> list[str]:
        """Return and clear queued memory-save notices."""
        notices = list(self._memory_notices)
        self._memory_notices.clear()
        return notices

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
        workdir: str | None = None,
    ) -> list[dict[str, Any]]:
        """List stored sessions, most recently used first.

        ``limit`` is applied in SQL rather than after fetching every session.
        This keeps the interactive ``:logs`` command fast on large histories.

        ``workdir`` restricts the listing to sessions whose final workdir
        (last ``[CWD]`` marker, else the project path) equals the given
        directory after path normalization; sessions with an unknown
        workdir never match. The filter is part of the WHERE clause, so
        ``limit`` applies after filtering.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if project is not None:
            clauses.append("s.project = ?")
            params.append(project)
        if principal_id is not None:
            clauses.append("s.principal_id = ?")
            params.append(principal_id)
        if workdir is not None:
            clauses.append("s.final_workdir_key = ?")
            params.append(normalize_workdir_key(workdir))
        if exclude_session_id is not None:
            clauses.append("s.session_id <> ?")
            params.append(exclude_session_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ?"
            params.append(max(0, int(limit)))

        rows = self._execute(
            "SELECT s.session_id, s.project, s.project_path, s.final_workdir, s.entry_point, "
            "s.created_at, s.last_used_at, s.principal_id, s.room_id, "
            "MAX(s.created_at, COALESCE(s.last_used_at, s.created_at), COALESCE((SELECT MAX(m.created_at) FROM messages m WHERE m.session_id = s.session_id), s.created_at)) AS last_activity_at, "
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
        # Legacy marker replays are idempotent and stay behind the
        # forget boundary (replay=True applies the content tombstone
        # check), so re-scanning the rewritten history cannot duplicate
        # or resurrect a local note. Scoped saves are skipped here: the
        # scoped store forgets by hard deletion, so there is no
        # tombstone to stop a re-scan from bringing a forgotten scoped
        # note back. Markers are detected when a message is written; a
        # rewrite is not a new write.
        for message in messages:
            if isinstance(message, dict):
                self._save_memory_marker(
                    str(message.get("content") or ""),
                    str(message.get("role") or ""),
                    allow_scoped=False,
                    replay=True,
                )

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
    def list_recent_exact_user_message_refs(
        self, session_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return recent, available user-message IDs without loading content."""
        self._require_session(session_id)
        rows = self._execute(
            "SELECT si.item_id AS ref_id, si.session_seq "
            "FROM session_items AS si JOIN messages AS m "
            "ON m.session_id = si.session_id "
            "AND CAST(m.message_id AS TEXT) = si.item_id "
            "WHERE si.session_id = ? AND si.item_kind = 'message' "
            "AND si.ordering_quality = 'exact' "
            "AND si.availability = 'available' AND m.role = 'user' "
            "AND TRIM(m.content, CHAR(9, 10, 11, 12, 13, 28, 29, 30, 31, 32, "
            "133, 160, 5760, 8192, 8193, 8194, 8195, 8196, 8197, 8198, "
            "8199, 8200, 8201, 8202, 8232, 8233, 8239, 8287, 12288)) <> '' "
            "ORDER BY si.session_seq DESC LIMIT ?",
            (session_id, max(0, limit)),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

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
    def invalidate_responses_continuation(self, session_id: str) -> None:
        """Persist a tombstone so :load cannot revive a stale provider chain."""
        self._require_session(session_id)
        self._execute(
            "INSERT INTO response_states(session_id, provider, model, response_id, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, "", "", "", "invalidated"),
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


# Opt-in attach/detach live in session_store_attach (it imports
# SessionStore from here at call time).
from .session_store_attach import (  # noqa: E402,F401
    attach_opt_in_session_store,
    detach_opt_in_session_store,
)
