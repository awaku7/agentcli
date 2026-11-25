"""AgentState persistence with revision checks. (``SessionStore`` mixin, split out of session_store.py)."""

from __future__ import annotations

from typing import Any
import json
import sqlite3

from .session_store_common import (
    SessionRevisionConflict,
    SessionStoreError,
    _db_locked,
    _is_owned_sub_agent_review_registry,
    _safe_json_dumps,
    _sanitize_value,
    _utc_now,
)


class _AgentStateMixin:
    """AgentState persistence with revision checks.

    Mixed into ``SessionStore``; relies on its connection, lock and
    ``_execute``/``_require_session`` helpers."""

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
            owner_row = self._execute(
                "SELECT 1 FROM sub_agent_review_registry_owners WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            value = dict(state)
            value.pop("structured_compaction", None)
            if owner_row is not None:
                # Only a SQLite ownership row can make a registry protected.
                # Prior releases allowed arbitrary JSON in this field.
                value.pop("sub_agent_review_registry", None)
            if current is not None:
                try:
                    previous = json.loads(current["state_json"])
                except (TypeError, ValueError):
                    previous = None
                if isinstance(previous, dict):
                    if "structured_compaction" in previous:
                        value["structured_compaction"] = previous[
                            "structured_compaction"
                        ]
                    if owner_row is not None:
                        owned = previous.get("sub_agent_review_registry")
                        if not _is_owned_sub_agent_review_registry(owned):
                            raise SessionStoreError(
                                "persisted reviewed receipt registry is invalid"
                            )
                        value["sub_agent_review_registry"] = owned
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
