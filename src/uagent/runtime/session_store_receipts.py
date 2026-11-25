"""Sub-Agent receipt review, application and commit. (``SessionStore`` mixin, split out of session_store.py)."""

from __future__ import annotations

from typing import Any
from typing import Callable
import json
import re
import sqlite3

from .compaction_record import CompactionValidationError
from .compaction_record import SourceRef
from .handoff_record import HandoffRecord
from .handoff_record import ProvenancedDeterministicDelta
from .session_store_common import (
    SessionRevisionConflict,
    SessionStoreError,
    _REVIEW_REGISTRY_OWNER,
    _db_locked,
    _is_owned_sub_agent_review_registry,
    _safe_json_dumps,
    _sanitize_value,
    _utc_now,
)


class _SubAgentReceiptMixin:
    """Sub-Agent receipt review, application and commit.

    Mixed into ``SessionStore``; relies on its connection, lock and
    ``_execute``/``_require_session`` helpers."""

    @_db_locked
    def review_sub_agent_receipt(
        self,
        receiving_session_id: str,
        root_handoff_id: str,
        *,
        reviewer_id: str,
        outcome: str,
        evidence_refs: tuple[SourceRef, ...],
        expected_revision: int,
        source_access_check: Callable[[SourceRef], bool],
    ) -> dict[str, Any]:
        """Record a host-authorized review, separate from Main AgentState.

        This records a reviewer assessment backed by independent Main-session
        user evidence. It does not independently establish factual truth,
        apply a HandoffRecord, complete any Goal, or change AgentState.
        """
        if not isinstance(root_handoff_id, str) or not root_handoff_id.strip():
            raise ValueError("root_handoff_id must be nonempty")
        if (
            not isinstance(reviewer_id, str)
            or re.fullmatch(r"[A-Za-z0-9._:@/-]{1,128}", reviewer_id) is None
        ):
            raise ValueError("reviewer_id must be a trusted reviewer identifier")
        if outcome not in {"supported", "rejected"}:
            raise ValueError("invalid receipt review outcome")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be non-negative")
        if (
            not isinstance(evidence_refs, tuple)
            or not 1 <= len(evidence_refs) <= 5
            or any(not isinstance(ref, SourceRef) for ref in evidence_refs)
            or len(set(evidence_refs)) != len(evidence_refs)
        ):
            raise ValueError("review requires 1-5 distinct SourceRefs")
        if not callable(source_access_check):
            raise TypeError("source_access_check must be callable")
        evidence_json = _safe_json_dumps(
            [ref.to_dict() for ref in evidence_refs],
            ensure_ascii=False,
            sort_keys=True,
        )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._require_session(receiving_session_id)
            existing = self._execute(
                "SELECT receiving_session_id, reviewer_id, outcome, "
                "evidence_refs_json, base_revision "
                "FROM sub_agent_receipt_reviews WHERE root_handoff_id = ?",
                (root_handoff_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["receiving_session_id"] != receiving_session_id
                    or existing["reviewer_id"] != reviewer_id
                    or existing["outcome"] != outcome
                    or existing["evidence_refs_json"] != evidence_json
                    or existing["base_revision"] != expected_revision
                ):
                    raise SessionStoreError("receipt has a different recorded review")
                self._connection.execute("COMMIT")
                return {
                    "root_handoff_id": root_handoff_id,
                    "outcome": outcome,
                    "already_reviewed": True,
                }
            receipt = self._execute(
                "SELECT source_session_id, record_json "
                "FROM sub_agent_receipts "
                "WHERE root_handoff_id = ? AND receiving_session_id = ?",
                (root_handoff_id, receiving_session_id),
            ).fetchone()
            if receipt is None:
                raise SessionStoreError("receipt is not owned by this Main Session")
            revision_row = self._execute(
                "SELECT revision FROM agent_states WHERE session_id = ?",
                (receiving_session_id,),
            ).fetchone()
            current_revision = (
                int(revision_row["revision"]) if revision_row is not None else 0
            )
            if current_revision != expected_revision:
                raise SessionRevisionConflict(
                    "Main AgentState revision changed before review"
                )
            try:
                record = HandoffRecord.from_dict(json.loads(receipt["record_json"]))
            except (TypeError, ValueError, CompactionValidationError) as exc:
                raise SessionStoreError("stored receipt is invalid") from exc
            if (
                record.root_handoff_id != root_handoff_id
                or record.receiving_session_id != receiving_session_id
                or len(record.findings) != 1
                or len(record.findings[0].source_refs) != 1
            ):
                raise SessionStoreError("stored receipt has invalid lineage")
            child_source = record.findings[0].source_refs[0]
            if (
                child_source.kind != "message"
                or child_source.scope_id != receipt["source_session_id"]
                or not self.is_exact_indexed_message_available(child_source)
            ):
                raise SessionStoreError("original child report is no longer available")
            for ref in evidence_refs:
                if (
                    ref.kind != "message"
                    or ref.scope_id != receiving_session_id
                    or not self.is_exact_indexed_message_available(ref)
                    or source_access_check(ref) is not True
                ):
                    raise SessionStoreError(
                        "review evidence is unavailable or unauthorized"
                    )
                row = self._execute(
                    "SELECT role, content FROM messages "
                    "WHERE message_id = CAST(? AS INTEGER) "
                    "AND CAST(message_id AS TEXT) = ? AND session_id = ?",
                    (ref.ref_id, ref.ref_id, receiving_session_id),
                ).fetchone()
                if row is None or row["role"] != "user" or not row["content"].strip():
                    raise SessionStoreError(
                        "review evidence must be a separate Main user message"
                    )
            self._execute(
                "INSERT INTO sub_agent_receipt_reviews ("
                "root_handoff_id, receiving_session_id, reviewer_id, "
                "outcome, evidence_refs_json, base_revision, reviewed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    root_handoff_id,
                    receiving_session_id,
                    reviewer_id,
                    outcome,
                    evidence_json,
                    expected_revision,
                    _utc_now(),
                ),
            )
            self._connection.execute("COMMIT")
            return {
                "root_handoff_id": root_handoff_id,
                "outcome": outcome,
                "already_reviewed": False,
            }
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def apply_reviewed_sub_agent_receipt(
        self,
        receiving_session_id: str,
        root_handoff_id: str,
        *,
        expected_revision: int,
        source_access_check: Callable[[SourceRef], bool],
    ) -> dict[str, Any]:
        """Atomically register a reviewed root in protected Main AgentState.

        Only host-authorized review metadata is applied, never model-written
        text, Goal status, factual conclusions, or the child state delta.
        A 'supported' review is still a human assessment, not proof of fact.
        """
        if not isinstance(root_handoff_id, str) or not root_handoff_id.strip():
            raise ValueError("root_handoff_id must be nonempty")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a non-negative integer")
        if not callable(source_access_check):
            raise TypeError("source_access_check must be callable")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._require_session(receiving_session_id)
            review = self._execute(
                "SELECT r.reviewer_id, r.outcome, r.evidence_refs_json, "
                "r.base_revision, p.source_session_id, p.record_json "
                "FROM sub_agent_receipt_reviews AS r "
                "JOIN sub_agent_receipts AS p "
                "ON p.root_handoff_id = r.root_handoff_id "
                "WHERE r.root_handoff_id = ? AND r.receiving_session_id = ? "
                "AND p.receiving_session_id = ?",
                (root_handoff_id, receiving_session_id, receiving_session_id),
            ).fetchone()
            if review is None:
                raise SessionStoreError("no review owned by this Main Session")
            if review["outcome"] != "supported":
                raise SessionStoreError("receipt review is not supported")
            try:
                evidence = json.loads(review["evidence_refs_json"])
                if not isinstance(evidence, list) or not 1 <= len(evidence) <= 5:
                    raise ValueError("invalid review evidence")
                evidence_refs = tuple(SourceRef.from_dict(value) for value in evidence)
                receipt = HandoffRecord.from_dict(json.loads(review["record_json"]))
            except (TypeError, ValueError, CompactionValidationError) as exc:
                raise SessionStoreError(
                    "review or receipt has invalid provenance"
                ) from exc
            if (
                len(set(evidence_refs)) != len(evidence_refs)
                or receipt.root_handoff_id != root_handoff_id
                or receipt.receiving_session_id != receiving_session_id
                or receipt.handoff_id != root_handoff_id
                or receipt.application_base_revision != receipt.receiving_base_revision
                or len(receipt.findings) != 1
                or len(receipt.findings[0].source_refs) != 1
                or receipt.work_done
                or receipt.decisions
                or receipt.unresolved
                or receipt.recommended_next_steps
                or receipt.artifact_refs
                or receipt.source_checkpoint_id is not None
                or receipt.state_delta != ProvenancedDeterministicDelta()
            ):
                raise SessionStoreError("receipt has invalid read-only lineage")

            current = self._execute(
                "SELECT state_json, revision FROM agent_states WHERE session_id = ?",
                (receiving_session_id,),
            ).fetchone()
            current_revision = int(current["revision"]) if current else 0
            try:
                state = json.loads(current["state_json"]) if current else {}
            except (TypeError, ValueError) as exc:
                raise SessionStoreError("stored AgentState is invalid JSON") from exc
            if not isinstance(state, dict):
                raise SessionStoreError("stored AgentState is not an object")
            owner_row = self._execute(
                "SELECT 1 FROM sub_agent_review_registry_owners WHERE session_id = ?",
                (receiving_session_id,),
            ).fetchone()
            registry = state.get("sub_agent_review_registry")
            if owner_row is None and "sub_agent_review_registry" in state:
                # Before this feature, callers could store arbitrary values
                # under this name. Preserve those values instead of trapping
                # existing sessions with an unremovable incompatible key.
                key = "legacy_sub_agent_review_registry"
                suffix = 2
                while key in state:
                    key = f"legacy_sub_agent_review_registry_{suffix}"
                    suffix += 1
                state[key] = registry
                registry = None
            if owner_row is None:
                registry = {
                    "owner": _REVIEW_REGISTRY_OWNER,
                    "schema_version": 1,
                    "entries": {},
                }
            if not _is_owned_sub_agent_review_registry(registry):
                raise SessionStoreError("unsupported reviewed receipt registry")
            entries = dict(registry["entries"])
            entry = {
                "status": "reviewed_unverified",
                "reviewer_id": review["reviewer_id"],
                "review_base_revision": review["base_revision"],
                "evidence_refs": [ref.to_dict() for ref in evidence_refs],
            }
            if root_handoff_id in entries:
                if entries[root_handoff_id] != entry:
                    raise SessionStoreError(
                        "reviewed root already has a different application"
                    )
                self._connection.execute("COMMIT")
                return {
                    "root_handoff_id": root_handoff_id,
                    "already_applied": True,
                    "result_revision": current_revision,
                }
            if current_revision != expected_revision:
                raise SessionRevisionConflict(
                    f"expected AgentState revision {expected_revision}, "
                    f"found {current_revision}"
                )
            child_ref = receipt.findings[0].source_refs[0]
            if (
                child_ref.kind != "message"
                or child_ref.scope_id != review["source_session_id"]
                or not self.is_exact_indexed_message_available(child_ref)
            ):
                raise SessionStoreError("original child output is unavailable")
            for ref in evidence_refs:
                if (
                    ref.kind != "message"
                    or ref.scope_id != receiving_session_id
                    or not self.is_exact_indexed_message_available(ref)
                    or source_access_check(ref) is not True
                ):
                    raise SessionStoreError(
                        "review evidence is unavailable or unauthorized"
                    )
                source = self._execute(
                    "SELECT role, content FROM messages "
                    "WHERE message_id = CAST(? AS INTEGER) "
                    "AND CAST(message_id AS TEXT) = ? AND session_id = ?",
                    (ref.ref_id, ref.ref_id, receiving_session_id),
                ).fetchone()
                if (
                    source is None
                    or source["role"] != "user"
                    or not source["content"].strip()
                ):
                    raise SessionStoreError(
                        "review evidence is not an independent user message"
                    )
            entries[root_handoff_id] = entry
            state["sub_agent_review_registry"] = {
                "owner": _REVIEW_REGISTRY_OWNER,
                "schema_version": 1,
                "entries": entries,
            }
            updated_at = _utc_now()
            state["updated_at"] = updated_at
            payload = _safe_json_dumps(
                _sanitize_value(state), ensure_ascii=False, sort_keys=True
            )
            next_revision = current_revision + 1
            if current is None:
                self._execute(
                    "INSERT INTO agent_states("
                    "session_id, state_json, updated_at, revision, updated_by_client"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (receiving_session_id, payload, updated_at, next_revision, None),
                )
            else:
                cursor = self._execute(
                    "UPDATE agent_states SET state_json = ?, updated_at = ?, "
                    "revision = ? WHERE session_id = ? AND revision = ?",
                    (
                        payload,
                        updated_at,
                        next_revision,
                        receiving_session_id,
                        current_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise SessionRevisionConflict(
                        "AgentState revision changed during review application"
                    )
            if owner_row is None:
                self._execute(
                    "INSERT INTO sub_agent_review_registry_owners("
                    "session_id, created_at) VALUES (?, ?)",
                    (receiving_session_id, updated_at),
                )
            self._connection.execute("COMMIT")
            return {
                "root_handoff_id": root_handoff_id,
                "already_applied": False,
                "result_revision": next_revision,
            }
        except Exception:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    @_db_locked
    def get_sub_agent_receipt_review(
        self, receiving_session_id: str, root_handoff_id: str
    ) -> dict[str, Any] | None:
        """Return review audit metadata, with current evidence availability."""
        self._require_session(receiving_session_id)
        row = self._execute(
            "SELECT reviewer_id, outcome, evidence_refs_json, "
            "base_revision, reviewed_at FROM sub_agent_receipt_reviews "
            "WHERE root_handoff_id = ? AND receiving_session_id = ?",
            (root_handoff_id, receiving_session_id),
        ).fetchone()
        if row is None:
            return None
        try:
            refs = tuple(
                SourceRef.from_dict(value)
                for value in json.loads(row["evidence_refs_json"])
            )
        except (TypeError, ValueError, CompactionValidationError):
            return None
        evidence_available = bool(refs)
        for ref in refs:
            if (
                ref.kind != "message"
                or ref.scope_id != receiving_session_id
                or not self.is_exact_indexed_message_available(ref)
            ):
                evidence_available = False
                break
            message = self._execute(
                "SELECT role, content FROM messages "
                "WHERE message_id = CAST(? AS INTEGER) "
                "AND CAST(message_id AS TEXT) = ? AND session_id = ?",
                (ref.ref_id, ref.ref_id, receiving_session_id),
            ).fetchone()
            if (
                message is None
                or message["role"] != "user"
                or not message["content"].strip()
            ):
                evidence_available = False
                break
        return {
            "root_handoff_id": root_handoff_id,
            "reviewer_id": row["reviewer_id"],
            "outcome": row["outcome"],
            "evidence_refs": [ref.to_dict() for ref in refs],
            "evidence_available": evidence_available,
            "base_revision": row["base_revision"],
            "reviewed_at": row["reviewed_at"],
        }

    @_db_locked
    def list_visible_sub_agent_receipts(
        self, receiving_session_id: str, *, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Read bounded, currently accessible unverified receipts for Main.

        A receipt is historical evidence, never AgentState. The caller must
        supply the receiver's trusted Session ID. Each returned report must
        still have its exact indexed child output available; source removal
        or revoked availability hides the report even if its receipt remains.
        """
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("receipt limit must be between 1 and 10")
        self._require_session(receiving_session_id)
        visible: list[dict[str, Any]] = []
        offset = 0
        while len(visible) < limit:
            # Filter by *current* availability before enforcing the result
            # count. Newer revoked records must not hide older visible ones.
            rows = self._execute(
                "SELECT root_handoff_id, source_session_id, base_revision, "
                "record_json, received_at FROM sub_agent_receipts "
                "WHERE receiving_session_id = ? "
                "ORDER BY received_at DESC, root_handoff_id DESC LIMIT 50 OFFSET ?",
                (receiving_session_id, offset),
            ).fetchall()
            if not rows:
                break
            offset += len(rows)
            for row in rows:
                try:
                    record = HandoffRecord.from_dict(json.loads(row["record_json"]))
                except (TypeError, ValueError, CompactionValidationError):
                    continue
                if (
                    record.receiving_session_id != receiving_session_id
                    or record.root_handoff_id != row["root_handoff_id"]
                    or record.receiving_base_revision != row["base_revision"]
                    or record.handoff_id != record.root_handoff_id
                    or record.application_base_revision
                    != record.receiving_base_revision
                    or record.artifact_refs
                    or record.source_checkpoint_id is not None
                    or record.work_done
                    or record.decisions
                    or record.unresolved
                    or record.recommended_next_steps
                    or record.state_delta != ProvenancedDeterministicDelta()
                    or len(record.findings) != 1
                    or len(record.findings[0].source_refs) != 1
                    or not record.findings[0].text.startswith(
                        "Unverified Sub-Agent report ("
                    )
                    or record.agent_id != f"sub-agent:{record.root_handoff_id}"
                ):
                    continue
                source = record.findings[0].source_refs[0]
                if (
                    source.kind != "message"
                    or source.scope_id != row["source_session_id"]
                    or not self.is_exact_indexed_message_available(source)
                ):
                    continue
                review = self.get_sub_agent_receipt_review(
                    receiving_session_id, record.root_handoff_id
                )
                review_assessment = {
                    "status": "unreviewed",
                    "evidence_available": False,
                }
                if review is not None:
                    review_assessment = {
                        "status": (
                            review["outcome"]
                            if review["evidence_available"]
                            else "evidence_unavailable"
                        ),
                        "evidence_available": review["evidence_available"],
                    }
                visible.append(
                    {
                        "root_handoff_id": record.root_handoff_id,
                        "role": record.role,
                        "goal_ids": list(record.goal_ids),
                        "objective": record.objective,
                        "unverified_report": record.findings[0].text,
                        "source_ref": source.to_dict(),
                        "base_revision": record.receiving_base_revision,
                        "received_at": row["received_at"],
                        "review_assessment": review_assessment,
                    }
                )
                if len(visible) >= limit:
                    return visible
            if len(rows) < 50:
                break
        return visible

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

        Root-ID deduplication and source validation share one SQLite
        transaction. Persisted Job reports can be read-only evidence after
        Main advances; direct handoffs still require the original revision.
        This is not a Goal update, decision, or completion signal.
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
            if revision != record.receiving_base_revision and expected_job_id is None:
                # An explicitly delivered, persisted Job report is read-only
                # evidence. Its original revision remains part of provenance;
                # stale dispatches must never change Main AgentState.
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
