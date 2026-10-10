"""CLI foreground delivery of finished structured Job receipts.

The event itself is never a source of authority: owner and Job state come
from the trusted Job manager, and the Main receiver checks output provenance.
No AgentState, Goal completion or Auto-pilot decision is applied here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .compaction_record import SourceRef
from .session_store import SessionStore
from .sub_agent_jobs import SubAgentJobManager, SubAgentJobOwner


def deliver_cli_finished_job_notice(
    *,
    manager: SubAgentJobManager,
    owner: SubAgentJobOwner,
    notice: Mapping[str, Any],
    store: SessionStore,
) -> dict[str, Any] | None:
    """Receive only the current CLI owner's finished, indexed child output.

    A notice is a wake-up signal, not permission or proof of completion.
    Authorization and Job persistence are checked again inside the manager,
    and output ownership is checked once more by the receiver transaction.
    Session changes leave old Job notices untouched rather than rerouting.
    """
    if owner.entry_point != "cli" or notice.get("event") != "finished":
        return None
    notice_owner = notice.get("owner")
    if not isinstance(notice_owner, Mapping):
        return None
    for key in ("entry_point", "session_id", "room_id", "a2a_task_id"):
        if notice_owner.get(key) != getattr(owner, key):
            return None
    job_id = notice.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        return None

    def source_access_check(ref: SourceRef) -> bool:
        # Return-side evidence must be a concrete indexed child output. The
        # trusted dispatch and the receiver validate the exact child session.
        return (
            ref.kind == "message"
            and ref.scope_id != owner.session_id
            and store.is_exact_indexed_message_available(ref)
        )

    return manager.deliver_compact_handoff_to_main(
        owner=owner,
        job_id=job_id,
        source_access_check=source_access_check,
    )
