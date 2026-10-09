"""Caller-bounded context for handoff, without retrieval or state mutation.

Bounds are trusted runtime input, never model/tool arguments. Exact SourceRefs
are an upper bound; the caller also rechecks availability and authorization at
delivery. These helpers do not grant tool permissions or apply returned deltas.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Callable, Iterable, Mapping

from .compaction_record import (
    MAX_ITEMS_PER_SECTION,
    CompactionValidationError,
    ConstraintRecord,
    DecisionRecord,
    FactRecord,
    ProvenancedObservation,
    SourceRef,
    _nonnegative_int,
    _object_tuple,
    _source_ref_tuple,
    _text,
    _text_tuple,
)
from .compaction_reducer import STATE_KEY, STATE_SCHEMA_VERSION
from .handoff_record import HandoffRecord, _bounded_json

MAX_HANDOFF_CONTEXT_BYTES = 128_000
SourceAccessCheck = Callable[[SourceRef], bool]


@dataclass(frozen=True)
class HandoffBounds:
    """Dispatch snapshot and exact references the caller permits to leave scope."""

    receiving_session_id: str
    receiving_base_revision: int
    goal_ids: tuple[str, ...] = ()
    source_refs: tuple[SourceRef, ...] = ()
    max_bytes: int = 32_000

    def __post_init__(self) -> None:
        _text(self.receiving_session_id, "receiving_session_id")
        _nonnegative_int(self.receiving_base_revision, "receiving_base_revision")
        _nonnegative_int(self.max_bytes, "max_bytes")
        if not 0 < self.max_bytes <= MAX_HANDOFF_CONTEXT_BYTES:
            raise CompactionValidationError("invalid handoff context byte budget")
        object.__setattr__(self, "goal_ids", _text_tuple(self.goal_ids, "goal_ids"))
        object.__setattr__(
            self, "source_refs", _source_ref_tuple(self.source_refs, "source_refs")
        )


def _refs(value: Any) -> Iterable[SourceRef]:
    if isinstance(value, SourceRef):
        yield value
    elif is_dataclass(value):
        for item in fields(value):
            yield from _refs(getattr(value, item.name))
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _refs(nested)
    elif isinstance(value, (tuple, list)):
        for nested in value:
            yield from _refs(nested)


def _check_sources(
    value: Any,
    bounds: HandoffBounds,
    source_access_check: SourceAccessCheck,
) -> None:
    allowed = set(bounds.source_refs)
    for ref in set(_refs(value)):
        # Check the entire reference, including kind, scope and sequence. Same
        # scope alone is not a capability to disclose every item in that scope.
        if ref not in allowed or source_access_check(ref) is not True:
            raise CompactionValidationError(
                "handoff source is unavailable or unauthorized"
            )


def project_sub_agent_return(
    record: HandoffRecord,
    *,
    bounds: HandoffBounds,
    source_access_check: SourceAccessCheck,
) -> str:
    """Return only validated compact evidence and refs, never Raw History.

    Rendering does not apply the evidence or make a completion judgment. The
    future receiver must atomically check revision and deduplicate root IDs.
    """
    if not isinstance(record, HandoffRecord):
        raise CompactionValidationError("return must be a HandoffRecord")
    if (
        record.receiving_session_id != bounds.receiving_session_id
        or record.receiving_base_revision != bounds.receiving_base_revision
    ):
        raise CompactionValidationError("handoff does not match dispatch snapshot")
    if not set(record.goal_ids) <= set(bounds.goal_ids):
        raise CompactionValidationError("handoff includes an out-of-scope goal")
    _check_sources(record, bounds, source_access_check)
    if record.source_checkpoint_id is not None:
        matches = [
            ref
            for ref in bounds.source_refs
            if ref.kind == "checkpoint" and ref.ref_id == record.source_checkpoint_id
        ]
        if len(matches) != 1:
            raise CompactionValidationError(
                "source checkpoint needs one scoped reference"
            )
        _check_sources(matches, bounds, source_access_check)
    return _bounded_json(record.to_dict(), bounds.max_bytes)


def _state_item(record_type: type, value: Any) -> Any:
    if not isinstance(value, dict):
        raise CompactionValidationError("goal evidence must be an object")
    # Reducer annotations are provenance bookkeeping, not model context. Only
    # named semantic fields go through the existing typed record validators.
    names = {item.name for item in fields(record_type)}
    return record_type.from_dict(
        {key: item for key, item in value.items() if key in names}
    )


def project_main_to_sub_agent(
    agent_state: Mapping[str, Any],
    *,
    objective: str,
    task_scope: str,
    goal_ids: tuple[str, ...],
    bounds: HandoffBounds,
    source_access_check: SourceAccessCheck,
    constraints: tuple[ConstraintRecord, ...] = (),
    checkpoint_refs: tuple[SourceRef, ...] = (),
    artifact_refs: tuple[SourceRef, ...] = (),
) -> str:
    """Project only selected current Goals and explicitly selected resources.

    Relevant checkpoints and required artifacts travel as references, not full
    payloads. No global narrative, Memory, history, provider state or unrelated
    Goal is copied. The caller owns subsequent authorized bounded retrieval.
    Accumulated evidence is selected per section (up to 50 items); observations
    keep their latest entries, lifecycle items prioritize active/tentative
    entries. Nonzero omitted_evidence counts mark an incomplete projection and
    must not be interpreted as a complete list of current constraints or work.
    """
    _text(objective, "objective")
    _text(task_scope, "task_scope")
    selected = _text_tuple(goal_ids, "goal_ids")
    if not set(selected) <= set(bounds.goal_ids):
        raise CompactionValidationError("projection includes an out-of-scope goal")
    constraints = _object_tuple(constraints, "constraints", ConstraintRecord)
    checkpoint_refs = _source_ref_tuple(checkpoint_refs, "checkpoint_refs")
    artifact_refs = _source_ref_tuple(artifact_refs, "artifact_refs")
    if any(ref.kind != "checkpoint" for ref in checkpoint_refs):
        raise CompactionValidationError("checkpoint_refs must reference checkpoints")
    if any(ref.kind != "artifact" for ref in artifact_refs):
        raise CompactionValidationError("artifact_refs must reference artifacts")
    if not isinstance(agent_state, Mapping):
        raise CompactionValidationError("agent_state must be a mapping")
    structured = agent_state.get(STATE_KEY, {})
    if not isinstance(structured, Mapping):
        raise CompactionValidationError("invalid structured AgentState")
    if selected and (
        type(structured.get("schema_version")) is not int
        or structured["schema_version"] != STATE_SCHEMA_VERSION
    ):
        raise CompactionValidationError("unsupported structured AgentState schema")
    goals = structured.get("goals", {})
    if not isinstance(goals, Mapping):
        raise CompactionValidationError("invalid structured Goals")

    projected_goals = []
    for goal_id in selected:
        goal = goals.get(goal_id)
        if not isinstance(goal, Mapping):
            raise CompactionValidationError("unknown selected goal")
        title = goal.get("title")
        _text(title, "goal.title", optional=True)
        projection = {"goal_id": goal_id, "title": title}
        omitted_evidence = {}
        for name, record_type, keyed in (
            ("status_observations", ProvenancedObservation, False),
            ("progress_events", ProvenancedObservation, False),
            ("next_action_observations", ProvenancedObservation, False),
            ("decisions", DecisionRecord, True),
            ("constraints", ConstraintRecord, True),
            ("facts", FactRecord, True),
        ):
            raw_items = goal.get(name, {} if keyed else [])
            if keyed:
                if not isinstance(raw_items, Mapping):
                    raise CompactionValidationError("invalid keyed goal evidence")
                raw_items = list(raw_items.values())
            if not isinstance(raw_items, (tuple, list)):
                raise CompactionValidationError("invalid goal evidence")
            # AgentState accumulates multiple valid records. Bound the outgoing
            # selection rather than rejecting its larger materialized lists.
            if len(raw_items) > MAX_ITEMS_PER_SECTION:
                omitted_evidence[name] = len(raw_items) - MAX_ITEMS_PER_SECTION
                if record_type in (DecisionRecord, ConstraintRecord):
                    # Keep current lifecycle items ahead of historical ones.
                    # Within each group preserve the materialized source order.
                    raw_items = sorted(
                        raw_items,
                        key=lambda item: (
                            isinstance(item, dict)
                            and item.get("status") in {"active", "tentative"}
                        ),
                    )
                raw_items = raw_items[-MAX_ITEMS_PER_SECTION:]
            items = tuple(_state_item(record_type, item) for item in raw_items)
            _check_sources(items, bounds, source_access_check)
            projection[name] = [item.to_dict() for item in items]
        if omitted_evidence:
            projection["omitted_evidence"] = omitted_evidence
        projected_goals.append(projection)
    _check_sources(
        (constraints, checkpoint_refs, artifact_refs), bounds, source_access_check
    )

    return _bounded_json(
        {
            "kind": "main_to_subagent",
            "receiving_session_id": bounds.receiving_session_id,
            "receiving_base_revision": bounds.receiving_base_revision,
            "application_base_revision": bounds.receiving_base_revision,
            "objective": objective,
            "task_scope": task_scope,
            "goals": projected_goals,
            "constraints": [item.to_dict() for item in constraints],
            "checkpoint_refs": [ref.to_dict() for ref in checkpoint_refs],
            "artifact_refs": [ref.to_dict() for ref in artifact_refs],
        },
        bounds.max_bytes,
    )
