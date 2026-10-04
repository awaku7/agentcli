"""Room-owned background Sub-Agent Jobs for the Web host."""

from __future__ import annotations

import json
from typing import Any

from ..runtime.sub_agent_jobs import (
    SubAgentConfirmationUnavailable,
    SubAgentJobExecutionContext,
    SubAgentJobManager,
    SubAgentJobOwner,
)
from .rooms import WebRoom, web_manager


def web_job_owner(room: WebRoom, session_id: str = "") -> SubAgentJobOwner | None:
    """Build an owner from a trusted room binding, never from tool arguments."""
    room_id = str(getattr(room, "room_id", "") or "").strip()
    bound_session = str(getattr(room, "session_id", "") or session_id or "").strip()
    if not room_id or not bound_session:
        return None
    return SubAgentJobOwner(
        entry_point="web", session_id=bound_session, room_id=room_id
    )


def get_web_job_runtime_context(turn: Any) -> tuple[Any, Any] | None:
    """Resolve the current Web room's manager and immutable owner."""
    from .rooms import get_context_web_room

    room = get_context_web_room()
    if room is None:
        return None
    turn_room_id = str(getattr(turn, "room_id", "") or "")
    if not turn_room_id or turn_room_id != str(room.room_id):
        return None
    session_id = str(getattr(turn, "session_id", "") or "")
    room_session = str(getattr(room, "session_id", "") or "")
    if room_session and session_id != room_session:
        return None
    owner = web_job_owner(room, session_id)
    manager = getattr(web_manager, "sub_agent_job_manager", None)
    if owner is None or manager is None:
        return None
    return manager, owner


def _web_confirmation_handler(
    context: SubAgentJobExecutionContext, message: str, is_password: bool
) -> str:
    context.raise_if_cancelled()
    room_id = context.owner.room_id
    if not room_id:
        raise SubAgentConfirmationUnavailable("Job owner has no Web room")
    room = web_manager.get_room(room_id)
    context.set_waiting_for_user(True)
    try:
        from .io import web_human_ask

        prompt = f"[Background Job {context.job_id} — {context.agent_name}]\n{message}"
        raw = web_human_ask(
            room,
            {
                "message": prompt,
                "is_password": is_password,
                "_job_id": context.job_id,
                "_cancel_event": context.cancel_event,
            },
        )
        context.raise_if_cancelled()
        try:
            result = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise SubAgentConfirmationUnavailable(
                "Web confirmation returned an invalid response"
            )
        if result.get("cancelled"):
            return "cancel"
        return str(result.get("user_reply") or "")
    finally:
        context.set_waiting_for_user(False)


def _web_job_notice(notice: dict[str, Any]) -> None:
    owner = notice.get("owner") or {}
    room_id = str(owner.get("room_id") or "").strip()
    if not room_id:
        return
    room = web_manager.get_room(room_id)
    event = str(notice.get("event") or "")
    job_id = str(notice.get("job_id") or "")
    agent = str(notice.get("agent_name") or "Sub-Agent")
    state = str(notice.get("state") or "unknown")
    if event == "started":
        content = f"[Background Job {job_id}] {agent} started."
    elif event == "finished":
        content = f"[Background Job {job_id}] {agent} {state}."
        reason = str(notice.get("reason") or "").strip()
        if reason:
            content += f" ({reason[:300]})"
    else:
        return
    room.add_message({"role": "assistant", "name": "Sub-Agent Job", "content": content})
    try:
        manager = getattr(web_manager, "sub_agent_job_manager", None)
        if manager is not None:
            owner_obj = web_job_owner(room, str(owner.get("session_id") or ""))
            if owner_obj is not None:
                jobs = manager.summary(owner=owner_obj)
                if room.loop:
                    import asyncio

                    asyncio.run_coroutine_threadsafe(
                        room.broadcast({"type": "job_snapshot", "jobs": jobs}),
                        room.loop,
                    )
    except Exception:
        pass


def initialize_web_job_runtime() -> SubAgentJobManager:
    """Create the Web process Job pool once, with room-aware notice/ask routes."""
    manager = getattr(web_manager, "sub_agent_job_manager", None)
    if manager is not None and not getattr(manager, "_closed", False):
        return manager
    manager = SubAgentJobManager(
        notice_callback=_web_job_notice,
        confirmation_handler=_web_confirmation_handler,
    )
    web_manager.sub_agent_job_manager = manager
    return manager


def shutdown_web_job_runtime() -> None:
    manager = getattr(web_manager, "sub_agent_job_manager", None)
    if manager is None:
        return
    try:
        manager.shutdown()
    finally:
        web_manager.sub_agent_job_manager = None


__all__ = [
    "get_web_job_runtime_context",
    "initialize_web_job_runtime",
    "shutdown_web_job_runtime",
    "web_job_owner",
]
