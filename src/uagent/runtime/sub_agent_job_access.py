"""Trusted entry-point gate for integrated Sub-Agent Job hosts."""

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


def get_job_runtime_context() -> tuple[Any, Any] | None:
    """Return an owner-bound manager only for a foreground integrated host turn."""
    turn = get_current_turn_context()
    if turn is None or current_sub_agent_job_mode() == "background":
        return None
    if get_active_sub_agent_name():
        return None
    if turn.entry_point == "cli":
        return get_cli_job_runtime_context()
    if turn.entry_point == "web":
        if not turn.authenticated:
            return None
        try:
            from ..web_impl.sub_agent_jobs import get_web_job_runtime_context

            return get_web_job_runtime_context(turn)
        except Exception:
            return None
    if turn.entry_point == "gui":
        if not turn.authenticated:
            return None
        try:
            from .. import core

            manager = getattr(core, "_sub_agent_job_manager", None)
            owner = getattr(core, "_sub_agent_job_owner", None)
        except Exception:
            return None
        if (
            manager is None
            or owner is None
            or getattr(owner, "entry_point", None) != "gui"
        ):
            return None
        turn_session_id = str(getattr(turn, "session_id", "") or "")
        if turn_session_id and turn_session_id != getattr(owner, "session_id", None):
            return None
        return manager, owner
    return None


__all__ = ["get_cli_job_runtime_context", "get_job_runtime_context"]
