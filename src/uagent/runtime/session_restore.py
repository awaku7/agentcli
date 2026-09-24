"""Host-side application of a prepared session restore plan."""

from __future__ import annotations

from typing import Any, Callable

from .agent_state import AgentState, AgentStateManager
from .session_command_service import SessionRestorePlan


def bind_session(
    core: Any,
    session_id: str,
    store: Any,
    *,
    callbacks_factory: Callable[[], Any] | None = None,
) -> None:
    """Bind a loaded session to core and optional tool callbacks."""
    core.session_id = session_id
    core._session_store_active_id = session_id
    try:
        if callbacks_factory is None:
            from ..tools.context import get_callbacks

            callbacks_factory = get_callbacks
        callbacks = callbacks_factory()
        callbacks.session_id = session_id
        callbacks.session_store = store
    except Exception:
        pass


def clear_response_continuation_state(core: Any) -> None:
    """Drop provider continuation IDs before switching to unrelated history."""
    response_state = getattr(core, "responses_state", None)
    if not isinstance(response_state, dict):
        return
    for key in (
        "previous_response_id",
        "active_response_id",
        "_stale_rid_occurred",
        "last_response_status",
    ):
        response_state.pop(key, None)


def apply_persisted_state(core: Any, plan: SessionRestorePlan) -> None:
    """Apply tool, agent, and Responses continuation state to a host core."""
    if plan.agent_state is not None:
        try:
            state = AgentState.from_dict(plan.agent_state)
            core.agent_state_manager = AgentStateManager(state)
            core.mcp_request_generation = state.mcp_request_generation
        except Exception:
            # A malformed optional agent-state record must not block loading the
            # conversation; the host starts a fresh runtime generation instead.
            core.agent_state_manager = AgentStateManager()
            core.mcp_request_generation = 0
    if hasattr(core, "tool_context"):
        core.tool_context.clear()
        core.tool_context.update(plan.tool_context)
    response_state = getattr(core, "responses_state", None)
    if isinstance(response_state, dict):
        clear_response_continuation_state(core)
    state = plan.response_state
    if state is None:
        return
    if isinstance(response_state, dict):
        response_state.update(
            {
                "provider": state["provider"],
                "model": state["model"],
                "previous_response_id": state["response_id"],
                "last_response_status": state["status"],
            }
        )


__all__ = [
    "apply_persisted_state",
    "bind_session",
    "clear_response_continuation_state",
]
