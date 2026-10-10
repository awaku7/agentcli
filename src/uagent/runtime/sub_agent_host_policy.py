"""Explicit, host-owned allowlists for structured Sub-Agent Job dispatch.

No model/tool request may choose Goal IDs, source references, authorization
callbacks or the receiving Session. All options are captured from trusted host
configuration. CLI integration is opt-in and defaults to no Goals or sources.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Callable

from .compaction_record import CompactionValidationError, SourceRef
from .session_store import SessionStore
from .sub_agent_handoff import SubAgentDispatch, capture_sub_agent_dispatch
from .sub_agent_jobs import SubAgentJobOwner

_CLI_OPT_IN = "UAGENT_SUB_AGENT_STRUCTURED_HANDOFF"
_CLI_GOALS = "UAGENT_SUB_AGENT_HANDOFF_GOAL_IDS"
_CLI_SOURCES = "UAGENT_SUB_AGENT_HANDOFF_SOURCE_REFS"
_ENABLED = frozenset({"1", "true", "yes", "on"})
_DISABLED = frozenset({"", "0", "false", "no", "off"})


def _configuration_array(environment: Mapping[str, str], name: str) -> list[object]:
    raw = environment.get(name, "[]")
    if not isinstance(raw, str) or len(raw) > 16_384:
        raise ValueError(f"{name} must be a short JSON array")
    try:
        items = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a JSON array") from exc
    if not isinstance(items, list) or len(items) > 50:
        raise ValueError(f"{name} must be a JSON array with at most 50 items")
    return items


def build_scoped_job_handoff_policy(
    store: SessionStore,
    *,
    entry_point: str,
    goal_ids: tuple[str, ...] = (),
    source_refs: tuple[SourceRef, ...] = (),
) -> Callable[[SubAgentJobOwner, str, str], SubAgentDispatch]:
    """Build a host-only dispatch policy with exact Goal/source allowlists."""
    if not isinstance(store, SessionStore):
        raise TypeError("structured handoff requires a persistent SessionStore")
    if not isinstance(entry_point, str) or not entry_point.strip():
        raise ValueError("entry_point is required")
    if not isinstance(goal_ids, tuple) or any(
        not isinstance(value, str) or not value.strip() for value in goal_ids
    ):
        raise ValueError("goal_ids must contain trusted nonempty strings")
    if len(goal_ids) != len(set(goal_ids)) or len(goal_ids) > 50:
        raise ValueError("goal_ids must be unique and bounded")
    if not isinstance(source_refs, tuple) or any(
        not isinstance(ref, SourceRef) or ref.kind != "message" for ref in source_refs
    ):
        raise ValueError("only indexed message SourceRefs are supported")
    if len(source_refs) != len(set(source_refs)) or len(source_refs) > 50:
        raise ValueError("source_refs must be unique and bounded")
    permitted_entry = entry_point.strip().lower()
    scoped_goals = tuple(goal_ids)
    scoped_sources = tuple(source_refs)
    selected = frozenset(scoped_sources)

    def policy(
        owner: SubAgentJobOwner, _agent_name: str, task: str
    ) -> SubAgentDispatch:
        if not isinstance(owner, SubAgentJobOwner):
            raise CompactionValidationError("invalid trusted Job owner")
        if owner.entry_point != permitted_entry:
            raise CompactionValidationError("Job owner entry point is not permitted")
        parent = store.get_session(owner.session_id)
        if parent["entry_point"] != owner.entry_point:
            raise CompactionValidationError("Job owner does not match parent Session")
        if parent["room_id"] != owner.room_id:
            raise CompactionValidationError("Job owner room does not match Session")
        if any(ref.scope_id != owner.session_id for ref in scoped_sources):
            raise CompactionValidationError(
                "selected source belongs to another Session"
            )

        def check_source(ref: SourceRef) -> bool:
            if ref not in selected or ref.kind != "message":
                return False
            # Re-evaluate the exact id and sequence, not merely the scope.
            # Legacy ordering or deleted sources must not be disclosed.
            return any(
                item["ref_id"] == ref.ref_id
                and item["session_seq"] == ref.session_seq
                and item["ordering_quality"] == "exact"
                and item["availability"] == "available"
                and item["message_id"] is not None
                for item in store.list_indexed_messages(owner.session_id)
            )

        if any(not check_source(ref) for ref in scoped_sources):
            raise CompactionValidationError("selected source is unavailable")
        return capture_sub_agent_dispatch(
            store,
            receiving_session_id=owner.session_id,
            objective=task,
            task_scope="Read-only investigation of the requested task",
            goal_ids=scoped_goals,
            source_refs=scoped_sources,
            source_access_check=check_source,
        )

    return policy


def cli_scoped_handoff_policy_from_environment(
    store: SessionStore | None,
    environment: Mapping[str, str],
) -> Callable[[SubAgentJobOwner, str, str], SubAgentDispatch] | None:
    """Opt-in CLI wiring; malformed opt-in fails closed instead of using legacy."""
    enabled = str(environment.get(_CLI_OPT_IN, "")).strip().lower()
    if enabled in _DISABLED:
        return None
    if enabled not in _ENABLED:
        raise ValueError(f"{_CLI_OPT_IN} must be 0 or 1")
    if not isinstance(store, SessionStore):
        raise ValueError("structured CLI handoff requires SessionStore")
    raw_goals = _configuration_array(environment, _CLI_GOALS)
    if any(not isinstance(item, str) or not item.strip() for item in raw_goals):
        raise ValueError(f"{_CLI_GOALS} must contain nonempty Goal IDs")
    raw_sources = _configuration_array(environment, _CLI_SOURCES)
    if any(not isinstance(item, dict) for item in raw_sources):
        raise ValueError(f"{_CLI_SOURCES} must contain SourceRef objects")
    try:
        source_refs = tuple(SourceRef.from_dict(item) for item in raw_sources)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{_CLI_SOURCES} contains an invalid SourceRef") from exc
    return build_scoped_job_handoff_policy(
        store,
        entry_point="cli",
        goal_ids=tuple(raw_goals),
        source_refs=source_refs,
    )
