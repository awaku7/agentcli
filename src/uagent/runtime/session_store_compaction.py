"""Compaction records. (``SessionStore`` mixin, split out of session_store.py)."""

from __future__ import annotations

from typing import Any
import json
import sqlite3

from .compaction_record import CompactionRecord
from .compaction_record import CompactionValidationError
from .compaction_reducer import CompactionReductionError
from .compaction_reducer import reduce_compaction_record
from .session_store_common import (
    SessionComparisonUnavailable,
    SessionRevisionConflict,
    SessionStoreError,
    _db_locked,
    _safe_json_dumps,
    _sanitize_value,
    _utc_now,
)


class _CompactionRecordMixin:
    """Compaction records.

    Mixed into ``SessionStore``; relies on its connection, lock and
    ``_execute``/``_require_session`` helpers."""

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
