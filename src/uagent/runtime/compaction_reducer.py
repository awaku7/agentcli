"""Deterministic reducer for validated Structured Compaction records.

The reducer writes only into the Structured Compaction namespace embedded in
AgentState. It never derives completion from narrative text and never applies
ambiguous Goal deltas without an explicit runtime authorization.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from typing import Any, Iterable

from .compaction_record import CompactionRecord, GoalDelta

STATE_KEY = "structured_compaction"
STATE_SCHEMA_VERSION = 1


class CompactionReductionError(ValueError):
    """Raised when a validated record cannot safely update current state."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_unique(items: list[Any], value: Any) -> None:
    marker = _canonical(value)
    if all(_canonical(existing) != marker for existing in items):
        items.append(value)


def _new_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "goals": {},
        "goal_delta_assignments": {},
        "shared_constraints": {},
        "shared_facts": {},
        "critical_context": {},
        "unresolved_goal_deltas": {},
        "narrative_continuation": [],
        "deterministic": {
            "read_files": [],
            "modified_files": [],
            "created_files": [],
            "deleted_files": [],
            "artifact_refs": [],
            "tool_call_refs": [],
            "subagent_refs": [],
            "executed_checks": [],
            "pending_operation_events": [],
            "tracking_coverage": [],
        },
        "applied_operations": [],
    }


def _goal_state(title: str | None) -> dict[str, Any]:
    return {
        "title": title,
        "status_observations": [],
        "progress_events": [],
        "decisions": {},
        "constraints": {},
        "facts": {},
        "next_action_observations": [],
        "applied_delta_ids": [],
    }


def _annotated(
    value: Any, *, operation_id: str, delta_id: str | None = None
) -> dict[str, Any]:
    item = value.to_dict()
    item["_operation_id"] = operation_id
    if delta_id is not None:
        item["_goal_delta_id"] = delta_id
    return item


def _insert_lifecycle_item(
    target: dict[str, Any],
    value: Any,
    *,
    operation_id: str,
    delta_id: str | None = None,
    status_field: str,
    superseded_status: str,
) -> None:
    item_id = (
        value.decision_id if hasattr(value, "decision_id") else value.constraint_id
    )
    serialized = _annotated(value, operation_id=operation_id, delta_id=delta_id)
    prior = target.get(item_id)
    if prior is not None:
        if _canonical(prior) != _canonical(serialized):
            raise CompactionReductionError(f"duplicate lifecycle item ID: {item_id}")
        return
    for superseded_id in value.supersedes:
        previous = target.get(superseded_id)
        if previous is None:
            raise CompactionReductionError(
                f"cannot supersede unknown lifecycle item: {superseded_id}"
            )
        # A reverted/revoked item stays inactive; superseding it must not
        # resurrect or rewrite its historical lifecycle.
        old_status = previous.get(status_field)
        if old_status not in {"reverted", "revoked"}:
            if value.status == "reverted":
                previous[status_field] = "reverted"
            elif value.status == "revoked":
                previous[status_field] = "revoked"
            else:
                previous[status_field] = superseded_status
    target[item_id] = serialized


def _apply_delta_content(
    goal: dict[str, Any],
    delta: GoalDelta,
    *,
    operation_id: str,
) -> None:
    delta_marker = f"{operation_id}:{delta.goal_delta_id}"
    if delta_marker in goal["applied_delta_ids"]:
        return

    for observation in delta.status_observations:
        _append_unique(
            goal["status_observations"],
            _annotated(
                observation, operation_id=operation_id, delta_id=delta.goal_delta_id
            ),
        )
    for observation in delta.progress_events:
        _append_unique(
            goal["progress_events"],
            _annotated(
                observation, operation_id=operation_id, delta_id=delta.goal_delta_id
            ),
        )
    for observation in delta.next_action_observations:
        _append_unique(
            goal["next_action_observations"],
            _annotated(
                observation, operation_id=operation_id, delta_id=delta.goal_delta_id
            ),
        )
    for decision in delta.decisions:
        _insert_lifecycle_item(
            goal["decisions"],
            decision,
            operation_id=operation_id,
            delta_id=delta.goal_delta_id,
            status_field="status",
            superseded_status="superseded",
        )
    for constraint in delta.constraints:
        _insert_lifecycle_item(
            goal["constraints"],
            constraint,
            operation_id=operation_id,
            delta_id=delta.goal_delta_id,
            status_field="status",
            superseded_status="superseded",
        )
    for fact in delta.facts:
        _insert_fact(
            goal["facts"],
            fact.fact_id,
            fact.to_dict(),
            operation_id,
            delta.goal_delta_id,
        )
    goal["applied_delta_ids"].append(delta_marker)


def _apply_goal_delta(
    state: dict[str, Any],
    record: CompactionRecord,
    delta: GoalDelta,
    *,
    authorized_resolution_ids: set[str],
) -> None:
    goals: dict[str, Any] = state["goals"]
    delta_key = f"{record.operation_id}:{delta.goal_delta_id}"

    if delta.association == "ambiguous":
        unknown_candidates = set(delta.candidate_goal_ids) - set(goals)
        if unknown_candidates:
            raise CompactionReductionError(
                f"ambiguous GoalDelta has unknown candidates: {sorted(unknown_candidates)}"
            )
        prior = state["unresolved_goal_deltas"].get(delta_key)
        entry = {
            "operation_id": record.operation_id,
            "goal_delta": delta.to_dict(),
            "resolution_status": "unresolved",
            "resolved_by": None,
        }
        if prior is not None and _canonical(prior) != _canonical(entry):
            raise CompactionReductionError("unresolved GoalDelta ID collision")
        state["unresolved_goal_deltas"][delta_key] = entry
        state["goal_delta_assignments"][delta_key] = None
        return

    if delta.association == "existing":
        goal_id = str(delta.goal_id)
        if goal_id not in goals:
            raise CompactionReductionError(f"unknown existing goal_id: {goal_id}")
        if delta.candidate_goal_ids and goal_id not in delta.candidate_goal_ids:
            raise CompactionReductionError(
                "existing goal_id is not included in candidate_goal_ids"
            )
    else:
        proposed_title = (delta.title_hint or "").strip().casefold()
        duplicates = [
            existing_id
            for existing_id, existing_goal in goals.items()
            if (existing_goal.get("title") or "").strip().casefold() == proposed_title
        ]
        if duplicates:
            raise CompactionReductionError(
                "new GoalDelta duplicates an existing title; use existing or ambiguous association"
            )
        # The deterministic ID makes retries of the same operation stable while
        # keeping LLM-proposed goal IDs out of the trusted state.
        goal_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"uag-structured-compaction:{record.session_id}:{record.operation_id}:{delta.goal_delta_id}",
            )
        )
        goals.setdefault(goal_id, _goal_state(delta.title_hint))

    goal = goals[goal_id]
    for unresolved_id in delta.resolves_ambiguous_delta_ids:
        if unresolved_id not in authorized_resolution_ids:
            raise CompactionReductionError(
                f"resolution lacks explicit runtime authorization: {unresolved_id}"
            )
        matches = [
            (key, entry)
            for key, entry in state["unresolved_goal_deltas"].items()
            if entry["goal_delta"]["goal_delta_id"] == unresolved_id
            and entry["resolution_status"] == "unresolved"
        ]
        if len(matches) != 1:
            raise CompactionReductionError(
                f"ambiguous or unknown unresolved GoalDelta: {unresolved_id}"
            )
        unresolved_key, unresolved = matches[0]
        unresolved_delta = GoalDelta.from_dict(unresolved["goal_delta"])
        unresolved["resolution_status"] = "resolved"
        unresolved["resolved_by"] = {
            "operation_id": record.operation_id,
            "goal_delta_id": delta.goal_delta_id,
            "goal_id": goal_id,
        }
        state["goal_delta_assignments"][unresolved_key] = goal_id
        # Once an explicit trusted resolution is supplied, fold the original
        # evidence into the selected goal without rewriting its source record.
        _apply_delta_content(
            goal,
            unresolved_delta,
            operation_id=unresolved["operation_id"],
        )

    state["goal_delta_assignments"][delta_key] = goal_id
    _apply_delta_content(goal, delta, operation_id=record.operation_id)


def _insert_fact(
    target: dict[str, Any],
    item_id: str,
    value: dict[str, Any],
    operation_id: str,
    delta_id: str | None,
) -> None:
    serialized = dict(value)
    serialized["_operation_id"] = operation_id
    if delta_id is not None:
        serialized["_goal_delta_id"] = delta_id
    prior = target.get(item_id)
    if prior is not None and _canonical(prior) != _canonical(serialized):
        raise CompactionReductionError(f"duplicate fact ID: {item_id}")
    target[item_id] = serialized


def reduce_compaction_record(
    agent_state: dict[str, Any] | None,
    record: CompactionRecord,
    *,
    authorized_resolution_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a new AgentState dictionary with one applied record folded in.

    Callers must perform revision checks and persistence in the same SQLite
    transaction. ``authorized_resolution_ids`` is a trusted runtime assertion
    of explicit user/alias evidence; model-produced text alone is insufficient.
    """
    if record.application_status != "applied":
        raise CompactionReductionError("comparison_only records are not reducible")
    base = deepcopy(agent_state or {})
    if not isinstance(base, dict):
        raise CompactionReductionError("AgentState must be a JSON object")
    current = base.get(STATE_KEY)
    if current is None:
        current = _new_state()
    elif (
        not isinstance(current, dict)
        or current.get("schema_version") != STATE_SCHEMA_VERSION
    ):
        raise CompactionReductionError("unsupported structured AgentState schema")
    else:
        current = deepcopy(current)

    if record.operation_id in current["applied_operations"]:
        base[STATE_KEY] = current
        return base

    # Delta IDs are stable within one operation; duplicates would make
    # authorization and idempotent projection ambiguous.
    delta_ids = [delta.goal_delta_id for delta in record.goal_deltas]
    if len(delta_ids) != len(set(delta_ids)):
        raise CompactionReductionError("duplicate goal_delta_id in CompactionRecord")

    # Resolution authorization is attached to the delta identified by its
    # goal_delta_id; the original evidence remains immutable in the audit state.
    authorized = set(str(item) for item in authorized_resolution_ids)
    for delta in record.goal_deltas:
        _apply_goal_delta(current, record, delta, authorized_resolution_ids=authorized)
    for constraint in record.shared_constraints:
        _insert_lifecycle_item(
            current["shared_constraints"],
            constraint,
            operation_id=record.operation_id,
            status_field="status",
            superseded_status="superseded",
        )
    for fact in record.shared_facts:
        _insert_fact(
            current["shared_facts"],
            fact.fact_id,
            fact.to_dict(),
            record.operation_id,
            None,
        )
    for fact in record.critical_context:
        _insert_fact(
            current["critical_context"],
            fact.fact_id,
            fact.to_dict(),
            record.operation_id,
            None,
        )
    for item in record.narrative_continuation:
        _append_unique(
            current["narrative_continuation"],
            _annotated(item, operation_id=record.operation_id),
        )

    deterministic = record.deterministic_delta.to_dict()
    for name in ("read_files", "modified_files", "created_files", "deleted_files"):
        for path in deterministic[name]:
            _append_unique(current["deterministic"][name], path)
    for name in (
        "artifact_refs",
        "tool_call_refs",
        "subagent_refs",
        "executed_checks",
        "pending_operation_events",
        "tracking_coverage",
    ):
        for item in deterministic[name]:
            _append_unique(
                current["deterministic"][name],
                {"operation_id": record.operation_id, "value": item},
            )
    current["applied_operations"].append(record.operation_id)
    base[STATE_KEY] = current
    return base


__all__ = [
    "CompactionReductionError",
    "STATE_KEY",
    "reduce_compaction_record",
]
