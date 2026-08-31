"""SQLite-backed session, message, and tool-call persistence."""

from __future__ import annotations

import atexit
import hashlib
import json
import ntpath
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils.paths import get_state_dir
from ..utils.secret_mask import mask_args


class SessionStoreError(RuntimeError):
    """Raised when session persistence cannot complete safely."""


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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                CREATE INDEX IF NOT EXISTS idx_response_states_session_id
                    ON response_states(session_id, state_id);
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
            message_columns = {
                row["name"]
                for row in self._connection.execute("PRAGMA table_info(messages)")
            }
            if "payload_json" not in message_columns:
                self._connection.execute(
                    "ALTER TABLE messages ADD COLUMN payload_json TEXT"
                )
        except sqlite3.Error as exc:
            raise SessionStoreError(
                f"could not initialize session store: {exc}"
            ) from exc

    def _execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        try:
            return self._connection.execute(sql, parameters)
        except sqlite3.Error as exc:
            raise SessionStoreError(f"session store operation failed: {exc}") from exc

    def _require_session(self, session_id: str) -> None:
        row = self._execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise SessionStoreError(f"unknown session: {session_id}")

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
            "SELECT session_id, project, project_key, project_path, entry_point, created_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise SessionStoreError(f"unknown session: {session_id}")
        return dict(row)

    @_db_locked
    def touch_session(self, session_id: str) -> None:
        """Mark a session as most recently used."""
        self._require_session(session_id)
        self._execute(
            "UPDATE sessions SET created_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE session_id = ?",
            (session_id,),
        )

    @_db_locked
    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> int:
        self._require_session(session_id)
        safe_content = redact_sensitive(content)
        safe_payload = None
        if payload is not None:
            try:
                safe_payload = json.dumps(
                    {**payload, "content": safe_content},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            except (TypeError, ValueError):
                safe_payload = json.dumps(
                    {"role": role, "content": safe_content}, ensure_ascii=False
                )
        # Keep the source row and FTS index in one transaction. Otherwise a
        # lock/error between the two INSERTs could leave search inconsistent.
        try:
            self._connection.execute("BEGIN")
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
                    self.append_message(
                        session.session_id, str(role), content, payload=message
                    )
        except Exception:
            try:
                self.delete_session(session.session_id)
            except Exception:
                pass
            raise
        self._execute(
            "INSERT INTO legacy_imports(source_path, session_id) VALUES (?, ?)",
            (source_key, session.session_id),
        )
        return session

    @_db_locked
    def list_sessions(
        self,
        *,
        project: str | None = None,
        limit: int | None = None,
        exclude_session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List stored sessions, newest first.

        ``limit`` is applied in SQL rather than after fetching every session.
        This keeps the interactive ``:logs`` command fast on large histories.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if project is not None:
            clauses.append("s.project = ?")
            params.append(project)
        if exclude_session_id is not None:
            clauses.append("s.session_id <> ?")
            params.append(exclude_session_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ?"
            params.append(max(0, int(limit)))

        rows = self._execute(
            "SELECT s.session_id, s.project, s.project_path, s.entry_point, s.created_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count, "
            "(SELECT content FROM messages m WHERE m.session_id = s.session_id AND m.role = 'user' ORDER BY message_id ASC LIMIT 1) AS first_message, "
            "(SELECT content FROM messages m WHERE m.session_id = s.session_id AND m.role = 'user' ORDER BY message_id DESC LIMIT 1) AS last_message, "
            "(SELECT summary FROM session_summaries ss WHERE ss.session_id = s.session_id) AS summary "
            "FROM sessions s"
            + where
            + " ORDER BY s.created_at DESC, s.rowid DESC"
            + limit_sql,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]

    @_db_locked
    def delete_session(self, session_id: str) -> None:
        """Delete one session and all of its persisted data."""
        self._require_session(session_id)
        try:
            self._connection.execute("BEGIN")
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
            self._connection.execute("BEGIN")
            self._execute(
                "DELETE FROM message_search WHERE session_id = ?", (session_id,)
            )
            self._execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._connection.execute("COMMIT")
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "")
                if role not in {"system", "user", "assistant", "tool"}:
                    continue
                self.append_message(
                    session_id, role, str(message.get("content") or ""), payload=message
                )
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
            safe_args_json = json.dumps(
                mask_args(args or {}), ensure_ascii=False, sort_keys=True
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
                redact_sensitive(str(reason or "")),
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
            safe_args = mask_args(args)
            args_json = json.dumps(safe_args, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise SessionStoreError(
                "tool-call arguments are not JSON serializable"
            ) from exc
        safe_result = redact_sensitive(result)
        existing = self._execute(
            "SELECT call_id FROM tool_calls WHERE call_id = ?", (call_id,)
        ).fetchone()
        if existing is not None:
            return str(existing["call_id"])
        self._execute(
            "INSERT INTO tool_calls(call_id, session_id, tool_name, args_json, result, status) VALUES (?, ?, ?, ?, ?, ?)",
            (call_id, session_id, tool_name, args_json, safe_result, status),
        )
        return call_id

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
        summary = redact_sensitive(summary).strip()
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
        parameters: list[Any] = [query, query_like, query_like, max(1, limit)]
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
    pending_tool_calls: dict[str, tuple[str, dict[str, Any]]] = {}

    jsonl_enabled = (
        os.environ.get("UAGENT_SESSION_BACKEND", "sqlite").strip().lower() != "sqlite"
    )

    def log_message(message: dict[str, Any]) -> None:
        if jsonl_enabled:
            original_log_message(message)
        role = message.get("role") if isinstance(message, dict) else None
        if role not in {"system", "user", "assistant", "tool"}:
            return
        content = str(message.get("content") or "")
        active_session_id = getattr(
            core, "_session_store_active_id", session.session_id
        )
        store.append_message(
            active_session_id,
            str(role),
            content,
            payload=message if isinstance(message, dict) else None,
        )
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

    core.log_message = log_message
    core.session_store = store
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
        for name in (
            "session_store",
            "session_id",
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
]
