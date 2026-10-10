"""Opt-in trusted dispatch snapshots and durable Sub-Agent result sources.

Hosts construct these objects outside model/tool arguments. This module does
not apply returns, reconcile revisions, grant tool access, or resume Auto-pilot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

from .compaction_record import CompactionValidationError, SourceRef
from .handoff_projection import (
    HandoffBounds,
    SourceAccessCheck,
    project_main_to_sub_agent,
)
from .session_store import SessionStore, redact_sensitive


def _persisted_compact_report(result: str) -> dict[str, str] | None:
    """Capture only redacted report fields before text-level SQLite masking.

    Masking serialized JSON can consume its closing quote or brace. The source
    message stays redacted; a safe structured snapshot supports compact return.
    """
    try:
        parsed = json.loads(result)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    status = parsed.get("status")
    summary = parsed.get("summary")
    if (
        not isinstance(summary, str)
        and isinstance(status, str)
        and status in {"error", "blocked", "incomplete"}
    ):
        summary = parsed.get("message")
    if not isinstance(status, str) or status not in {
        "completed",
        "error",
        "blocked",
        "incomplete",
    }:
        return None
    if not isinstance(summary, str):
        return None
    return {"status": status, "summary": redact_sensitive(summary)}


@dataclass(frozen=True)
class SubAgentDispatch:
    """One immutable receiver snapshot; authorization is rechecked at delivery."""

    dispatch_id: str
    source_session_id: str
    objective: str
    bounds: HandoffBounds
    _context_json: str = field(repr=False)
    _source_refs: tuple[SourceRef, ...] = field(repr=False)
    _source_access_check: SourceAccessCheck = field(repr=False, compare=False)
    _store: SessionStore = field(repr=False, compare=False)

    def render_context(self) -> str:
        for ref in self._source_refs:
            if self._source_access_check(ref) is not True:
                raise CompactionValidationError(
                    "handoff source is unavailable or unauthorized at delivery"
                )
        return self._context_json

    def _result_source(
        self, *, job_id: str | None = None, check_owner: bool = True
    ) -> SourceRef | None:
        for item in self._store.list_indexed_messages(self.source_session_id):
            if (
                item["role"] == "assistant"
                and (item["payload"] or {}).get("dispatch_id") == self.dispatch_id
            ):
                if (
                    check_owner
                    and (item["payload"] or {}).get("job_id") != job_id
                ):
                    raise CompactionValidationError(
                        "persisted Sub-Agent result belongs to another Job"
                    )
                return SourceRef(
                    kind="message",
                    scope_id=self.source_session_id,
                    ref_id=item["ref_id"],
                    session_seq=item["session_seq"],
                )
        return None

    def record_result(self, result: str, *, job_id: str | None = None) -> SourceRef:
        """Persist output, or recover a result owned by this same Job.

        The optional trusted Job ID is not model-controlled. It prevents a
        different Job from adopting an existing dispatch's indexed output on
        retries or when separate Job managers share one child session.
        """
        if job_id is not None and (not isinstance(job_id, str) or not job_id.strip()):
            raise CompactionValidationError("invalid trusted Job ID")
        existing = self._result_source(job_id=job_id)
        if existing is not None:
            return existing
        self._store.append_sub_agent_result_once(
            self.source_session_id,
            result,
            dispatch_id=self.dispatch_id,
            job_id=job_id,
            compact_report=_persisted_compact_report(result),
        )
        source = self._result_source(job_id=job_id)
        if source is not None:
            return source
        raise RuntimeError("persisted Sub-Agent output has no source index")


def capture_sub_agent_dispatch(
    store: SessionStore,
    *,
    receiving_session_id: str,
    objective: str,
    task_scope: str,
    goal_ids: tuple[str, ...] = (),
    source_refs: tuple[SourceRef, ...] = (),
    source_access_check: SourceAccessCheck,
    max_bytes: int = 32_000,
) -> SubAgentDispatch:
    """Capture revision and bounded context before worker execution/queuing.

    Selection and access checks belong to the trusted host, never tool args.
    The dedicated child session stores the dispatch lineage and output as indexed
    sources. It is not imported into Main history or applied as completion.
    """
    state, revision = store.get_agent_state_snapshot(receiving_session_id)
    bounds = HandoffBounds(
        receiving_session_id=receiving_session_id,
        receiving_base_revision=revision,
        goal_ids=goal_ids,
        source_refs=source_refs,
        max_bytes=max_bytes,
    )
    used_refs: set[SourceRef] = set()

    def check_source(ref: SourceRef) -> bool:
        allowed = source_access_check(ref)
        if allowed is True:
            used_refs.add(ref)
        return allowed

    context_json = project_main_to_sub_agent(
        state or {},
        objective=objective,
        task_scope=task_scope,
        goal_ids=goal_ids,
        bounds=bounds,
        source_access_check=check_source,
    )
    parent = store.get_session(receiving_session_id)
    dispatch_id = uuid4().hex
    child = store.create_session(
        project=parent["project"],
        project_path=parent["project_path"],
        entry_point="sub-agent",
    )
    try:
        if parent["principal_id"]:
            store.bind_identity_context(
                child.session_id,
                principal_id=parent["principal_id"],
                room_id=parent["room_id"] or "",
            )
        store.append_message(
            child.session_id,
            "user",
            context_json,
            payload={
                "dispatch_id": dispatch_id,
                "receiving_session_id": receiving_session_id,
                "receiving_base_revision": revision,
            },
        )
    except BaseException:
        # This new session has not been published to a worker/caller yet.
        # Remove its message, FTS and source-index rows on failed capture.
        store.delete_session(child.session_id)
        raise
    return SubAgentDispatch(
        dispatch_id=dispatch_id,
        source_session_id=child.session_id,
        objective=objective,
        bounds=bounds,
        _context_json=context_json,
        _source_refs=tuple(used_refs),
        _source_access_check=source_access_check,
        _store=store,
    )
