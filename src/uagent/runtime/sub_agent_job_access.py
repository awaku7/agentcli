"""Trusted entry-point gate for CLI-only Sub-Agent Job orchestration tools."""

from __future__ import annotations

from typing import Any

from .identity_context import get_current_turn_context
from .subagent_context import get_active_sub_agent_name
from .sub_agent_jobs import current_sub_agent_job_mode


def get_cli_job_runtime_context() -> tuple[Any, Any] | None:
    """Return the current CLI's manager and owner for the foreground Main Agent."""
    turn = get_current_turn_context()
    if turn is None or turn.entry_point != "cli":
        return None
    if current_sub_agent_job_mode() == "background" or get_active_sub_agent_name():
        return None
    try:
        from .. import core

        manager = getattr(core, "_sub_agent_job_manager", None)
        owner = getattr(core, "_sub_agent_job_owner", None)
    except Exception:
        return None
    if manager is None or owner is None or getattr(owner, "entry_point", None) != "cli":
        return None
    turn_session_id = str(getattr(turn, "session_id", "") or "")
    if turn_session_id and turn_session_id != getattr(owner, "session_id", None):
        return None
    return manager, owner


__all__ = ["get_cli_job_runtime_context"]
