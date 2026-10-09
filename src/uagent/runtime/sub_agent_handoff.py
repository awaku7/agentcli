"""Opt-in trusted dispatch snapshots and durable Sub-Agent result sources.

Hosts construct these objects outside model/tool arguments. This module does
not apply returns, reconcile revisions, grant tool access, or resume Auto-pilot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .compaction_record import CompactionValidationError, SourceRef
from .handoff_projection import (
    HandoffBounds,
    SourceAccessCheck,
    project_main_to_sub_agent,
)
from .session_store import SessionStore


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

    def _result_source(self) -> SourceRef | None:
        for item in self._store.list_indexed_messages(self.source_session_id):
            if (
                item["role"] == "assistant"
                and (item["payload"] or {}).get("dispatch_id") == self.dispatch_id
            ):
                return SourceRef(
                    kind="message",
                    scope_id=self.source_session_id,
                    ref_id=item["ref_id"],
                    session_seq=item["session_seq"],
                )
        return None

    def record_result(self, result: str) -> SourceRef:
        """Persist output, or recover its ref after an ambiguous storage error.

        Runner reservations serialize retries. This lookup does not implement
        cross-process deduplication or Main's transactional return application.
        """
        existing = self._result_source()
        if existing is not None:
            return existing
        self._store.append_message(
            self.source_session_id,
            "assistant",
            result,
            payload={"dispatch_id": self.dispatch_id},
        )
        source = self._result_source()
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
    child = store.create_session(
        project=parent["project"],
        project_path=parent["project_path"],
        entry_point="sub-agent",
    )
    dispatch_id = uuid4().hex
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
