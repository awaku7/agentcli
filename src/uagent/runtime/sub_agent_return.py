"""Read-only, provenance-checked compact return for a structured Sub-Agent.

The report is an untrusted statement made by the child, not a state delta or a
Main completion decision. Only trusted runtime arguments identify the dispatch,
role, receiver and source. This module never updates the receiving AgentState.
"""

from __future__ import annotations

import json

from .compaction_record import CompactionValidationError, SourceRef
from .handoff_projection import (
    HandoffBounds,
    SourceAccessCheck,
    project_sub_agent_return,
)
from .handoff_record import HandoffRecord, ProvenancedHandoffItem
from .sub_agent_handoff import SubAgentDispatch


def build_compact_sub_agent_return(
    dispatch: SubAgentDispatch,
    *,
    agent_role: str,
    source_access_check: SourceAccessCheck,
    max_bytes: int = 32_000,
) -> str:
    """Build a proposed return from exactly one persisted child output.

    Fail closed for missing, ambiguous or unauthorized output. Source authority
    comes from the child's indexed message, never IDs or claims in model JSON.
    Callers must still verify receiving revision and apply any changes in a
    separate atomic, idempotent transaction.
    """
    if not isinstance(dispatch, SubAgentDispatch):
        raise TypeError("dispatch must be trusted runtime input")
    if not isinstance(agent_role, str) or not agent_role.strip():
        raise CompactionValidationError("invalid trusted Sub-Agent role")
    if not callable(source_access_check):
        raise TypeError("source_access_check must be callable")

    store = dispatch._store
    child = store.get_session(dispatch.source_session_id)
    parent = store.get_session(dispatch.bounds.receiving_session_id)
    if (
        child["entry_point"] != "sub-agent"
        or child["project_key"] != parent["project_key"]
        or child["principal_id"] != parent["principal_id"]
        or child["room_id"] != parent["room_id"]
    ):
        raise CompactionValidationError("Sub-Agent return session scope mismatch")

    dispatch.render_context()  # Recheck grants captured from Main at delivery.
    messages = store.list_indexed_messages(dispatch.source_session_id)
    dispatch_messages = [
        item
        for item in messages
        if item["role"] == "user"
        and (item["payload"] or {}).get("dispatch_id") == dispatch.dispatch_id
        and (item["payload"] or {}).get("receiving_session_id")
        == dispatch.bounds.receiving_session_id
        and (item["payload"] or {}).get("receiving_base_revision")
        == dispatch.bounds.receiving_base_revision
    ]
    if (
        len(dispatch_messages) != 1
        or dispatch_messages[0]["ordering_quality"] != "exact"
    ):
        raise CompactionValidationError("missing or ambiguous trusted dispatch")

    outputs = [
        item
        for item in messages
        if item["role"] == "assistant"
        and (item["payload"] or {}).get("dispatch_id") == dispatch.dispatch_id
    ]
    if len(outputs) != 1 or outputs[0]["ordering_quality"] != "exact":
        raise CompactionValidationError("missing or ambiguous Sub-Agent output")
    output = outputs[0]
    source = SourceRef(
        kind="message",
        scope_id=dispatch.source_session_id,
        ref_id=output["ref_id"],
        session_seq=output["session_seq"],
    )
    if source_access_check(source) is not True:
        raise CompactionValidationError(
            "Sub-Agent output is unavailable or unauthorized"
        )

    # record_result stored a redacted structured snapshot beside the source.
    # The message text itself may no longer be parseable JSON after SQLite's
    # credential masking consumes JSON quotes. Older records use text fallback.
    report = (output["payload"] or {}).get("compact_report")
    if report is None:
        raw_output = output["content"]
        if not isinstance(raw_output, str):
            raise CompactionValidationError("invalid persisted Sub-Agent output")
        try:
            report = json.loads(raw_output)
        except (ValueError, TypeError) as exc:
            raise CompactionValidationError("Sub-Agent output is not JSON") from exc
    if not isinstance(report, dict):
        raise CompactionValidationError("Sub-Agent report must be an object")
    status = report.get("status")
    summary = report.get("summary")
    if not isinstance(status, str) or status not in {
        "completed",
        "error",
        "blocked",
        "incomplete",
    }:
        raise CompactionValidationError("invalid Sub-Agent report status")
    if not isinstance(summary, str) or not summary.strip():
        raise CompactionValidationError("Sub-Agent report requires a summary")

    # Child text is evidence of what the child reported, not verified success.
    # Ignore any model-supplied delivery IDs, source refs, decisions or deltas.
    record = HandoffRecord(
        handoff_id=dispatch.dispatch_id,
        root_handoff_id=dispatch.dispatch_id,
        receiving_session_id=dispatch.bounds.receiving_session_id,
        receiving_base_revision=dispatch.bounds.receiving_base_revision,
        application_base_revision=dispatch.bounds.receiving_base_revision,
        agent_id=f"sub-agent:{dispatch.dispatch_id}",
        role=agent_role,
        goal_ids=dispatch.bounds.goal_ids,
        objective=dispatch.objective,
        findings=(
            ProvenancedHandoffItem(
                text=f"Unverified Sub-Agent report ({status}): {summary}",
                source_refs=(source,),
            ),
        ),
    )
    bounds = HandoffBounds(
        receiving_session_id=dispatch.bounds.receiving_session_id,
        receiving_base_revision=dispatch.bounds.receiving_base_revision,
        goal_ids=dispatch.bounds.goal_ids,
        source_refs=(source,),
        max_bytes=max_bytes,
    )
    return project_sub_agent_return(
        record, bounds=bounds, source_access_check=source_access_check
    )
