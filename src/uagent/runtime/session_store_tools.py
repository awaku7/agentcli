"""Tool calls, tool results and tool context of a session. (``SessionStore`` mixin, split out of session_store.py)."""

from __future__ import annotations

from typing import Any
import json
import re
import sqlite3
import uuid

from ..utils.secret_mask import mask_args
from .tool_result_persistence import bounded_persistent_json
from .tool_result_persistence import sanitize_persistent_value
from .session_store_common import (
    SessionStoreError,
    _TOOL_RESULT_MAX_RECORD_BYTES,
    _TOOL_RESULT_MAX_SUMMARY_BYTES,
    _bounded_tool_result_metadata,
    _db_locked,
    _safe_json_dumps,
    _sanitize_text,
    _sanitize_value,
    _truncate_utf8_field,
    _utc_now,
    redact_sensitive,
)


class _ToolRecordsMixin:
    """Tool calls, tool results and tool context of a session.

    Mixed into ``SessionStore``; relies on its connection, lock and
    ``_execute``/``_require_session`` helpers."""

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
            result_id = _sanitize_text(str(record.get("result_id") or uuid.uuid4().hex))
            if sanitize_persistent_value(result_id) != result_id:
                raise SessionStoreError("tool result ID contains secret-looking data")
            if len(result_id.encode("utf-8", errors="replace")) > 256:
                raise SessionStoreError("tool result ID exceeds the 256-byte limit")
            task_id = _truncate_utf8_field(
                str(sanitize_persistent_value(record.get("task_id") or "")), 1024
            )
            tool_name = _truncate_utf8_field(
                str(sanitize_persistent_value(record.get("tool_name") or "tool")), 256
            )
            result_class = _truncate_utf8_field(
                str(sanitize_persistent_value(record.get("result_class") or "small")),
                32,
            )
            importance = _truncate_utf8_field(
                str(sanitize_persistent_value(record.get("importance") or "normal")),
                64,
            )
            created_at = _truncate_utf8_field(
                str(sanitize_persistent_value(record.get("created_at") or _utc_now())),
                64,
            )
        except SessionStoreError:
            raise
        except Exception as exc:
            raise SessionStoreError(
                "tool result identity metadata could not be safely sanitized"
            ) from exc
        try:
            metadata_json = _bounded_tool_result_metadata(record.get("metadata") or {})
            summary_value = sanitize_persistent_value(
                _sanitize_text(str(record.get("summary") or ""))
            )
            summary = _truncate_utf8_field(
                str(summary_value), _TOOL_RESULT_MAX_SUMMARY_BYTES
            )
            artifact_ref_value = sanitize_persistent_value(
                _sanitize_text(str(record.get("artifact_ref") or ""))
            )
            artifact_ref = _truncate_utf8_field(str(artifact_ref_value), 4096)
            safe_size_bytes = max(
                0,
                min(int(record.get("size_bytes") or 0), (1 << 63) - 1),
            )
            fixed_fields = (
                session_id,
                result_id,
                task_id,
                tool_name,
                result_class,
                str(safe_size_bytes),
                summary,
                artifact_ref,
                importance,
                metadata_json,
                created_at,
            )
            fixed_bytes = sum(
                len(str(field).encode("utf-8", errors="replace"))
                for field in fixed_fields
            )
            history_budget = max(0, _TOOL_RESULT_MAX_RECORD_BYTES - fixed_bytes - 128)
            persistent_json = bounded_persistent_json(
                _sanitize_value(persistent_history),
                history_budget,
                artifact_ref=artifact_ref,
            )
        except Exception:
            # Never fall back to serializing the unprocessed value. Keep only
            # inert metadata if redaction or serialization itself fails.
            fallback_metadata: dict[str, Any] = {
                "_uagent_metadata": "omitted_after_sanitization_error"
            }
            raw_metadata = record.get("metadata")
            if isinstance(raw_metadata, dict) and raw_metadata.get("status") in {
                "success",
                "failed",
                "timeout",
                "cancelled",
            }:
                fallback_metadata["status"] = raw_metadata["status"]
            metadata_json = _safe_json_dumps(fallback_metadata)
            summary = "[persisted summary omitted]"
            artifact_ref = ""
            safe_size_bytes = 0
            task_id = _truncate_utf8_field(task_id, 1024)
            tool_name = _truncate_utf8_field(tool_name, 256)
            result_class = _truncate_utf8_field(result_class, 32)
            importance = _truncate_utf8_field(importance, 64)
            persistent_json = _safe_json_dumps(
                {"_uagent_persisted_history": "omitted_after_sanitization_error"}
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            # Result IDs are only unique inside a session, so a repeat from
            # another conversation is a distinct result rather than a conflict.
            existing = self._execute(
                "SELECT result_id FROM tool_results "
                "WHERE session_id = ? AND result_id = ?",
                (session_id, result_id),
            ).fetchone()
            if existing is not None:
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
                    task_id,
                    tool_name,
                    result_class,
                    safe_size_bytes,
                    summary,
                    artifact_ref,
                    importance,
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
                "DELETE FROM tool_results WHERE session_id = ? "
                f"AND result_id IN ({placeholders})",
                (session_id, *ids),
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
            # Call IDs are only unique inside a session, so a repeat from
            # another conversation is a distinct call rather than a conflict.
            existing = self._execute(
                "SELECT call_id FROM tool_calls WHERE session_id = ? AND call_id = ?",
                (session_id, call_id),
            ).fetchone()
            if existing is not None:
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
