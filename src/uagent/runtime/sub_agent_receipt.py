"""Host-only receipt of a provenance-checked compact Sub-Agent return.

The child report remains unverified. Receipt persistence does not modify Main
AgentState, complete a Goal, or resume Auto-pilot.
"""

from __future__ import annotations

import json

from .handoff_record import HandoffRecord
from .handoff_projection import SourceAccessCheck
from .sub_agent_handoff import SubAgentDispatch
from .sub_agent_return import build_compact_sub_agent_return


def receive_compact_sub_agent_return(
    dispatch: SubAgentDispatch,
    *,
    agent_role: str,
    source_access_check: SourceAccessCheck,
    max_bytes: int = 32_000,
    expected_job_id: str | None = None,
) -> dict[str, object]:
    """Validate and durably receipt an indexed child output once.

    This entry point takes only runtime-owned dispatch data and an up-to-date
    authorization callback; callers must not derive those from model output.
    Main revision conflicts are not automatically rebased.
    """
    payload = build_compact_sub_agent_return(
        dispatch,
        agent_role=agent_role,
        source_access_check=source_access_check,
        max_bytes=max_bytes,
    )
    record = HandoffRecord.from_dict(json.loads(payload))
    return dispatch._store.commit_sub_agent_receipt(
        record,
        source_session_id=dispatch.source_session_id,
        expected_role=agent_role,
        source_access_check=source_access_check,
        expected_job_id=expected_job_id,
    )
