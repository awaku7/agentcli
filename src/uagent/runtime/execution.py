from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Callable, Iterator

from .lifecycle import (
    AgentLifecycle,
    InvalidLifecycleTransition,
    LifecycleSnapshot,
)
from .logging_setup import log_event

_CURRENT_LIFECYCLE: ContextVar[AgentLifecycle | None] = ContextVar(
    "uagent_current_lifecycle", default=None
)
_CURRENT_CALLBACK: ContextVar[Callable[[LifecycleSnapshot], None] | None] = ContextVar(
    "uagent_current_lifecycle_callback", default=None
)
_TOOL_RUNNER_ACTIVE: ContextVar[bool] = ContextVar(
    "uagent_tool_runner_active", default=False
)


def tool_runner_active() -> bool:
    """Whether execution is currently inside a centralized tool runner."""
    return _TOOL_RUNNER_ACTIVE.get()


def set_tool_runner_active(active: bool):
    """Set tool-runner status and return a token for reset()."""
    return _TOOL_RUNNER_ACTIVE.set(active)


def reset_tool_runner_active(token) -> None:
    _TOOL_RUNNER_ACTIVE.reset(token)

_LIFECYCLE_EVENTS = {
    "CREATED": "agent.created",
    "RUNNING": "agent.started",
    "WAITING_TOOL": "agent.waiting_tool",
    "COMPLETED": "agent.completed",
    "FAILED": "agent.failed",
    "CANCELLED": "agent.cancelled",
    "TIMEOUT": "agent.timeout",
    "PAUSED": "agent.paused",
}


@contextmanager
def lifecycle_execution(
    lifecycle: AgentLifecycle | None = None,
    *,
    cancel_exceptions: tuple[type[BaseException], ...] = (),
    on_transition: Callable[[LifecycleSnapshot], None] | None = None,
) -> Iterator[AgentLifecycle]:
    """Track one synchronous Agent execution with a shared lifecycle.

    The context manager deliberately treats cancellation-like exceptions as a
    cancelled execution and all other exceptions as failures. Invalid terminal
    transitions are ignored so a concurrent cancellation remains authoritative.
    """
    current = lifecycle or AgentLifecycle()
    lifecycle_token = _CURRENT_LIFECYCLE.set(current)
    callback_token = _CURRENT_CALLBACK.set(on_transition)
    if current.status.value == "CREATED":
        _emit_lifecycle_events(current.snapshot())
    _safe_transition(current, "start")
    try:
        try:
            yield current
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            _safe_transition(current, "cancel")
            raise
        except TimeoutError:
            _safe_transition(current, "timeout")
            raise
        except BaseException as exc:
            if cancel_exceptions and isinstance(exc, cancel_exceptions):
                _safe_transition(current, "cancel")
            else:
                _safe_transition(current, "fail")
            raise
        else:
            _safe_transition(current, "complete")
    finally:
        _CURRENT_CALLBACK.reset(callback_token)
        _CURRENT_LIFECYCLE.reset(lifecycle_token)


def current_lifecycle() -> AgentLifecycle | None:
    return _CURRENT_LIFECYCLE.get()


def mark_tool_waiting() -> None:
    lifecycle = current_lifecycle()
    if lifecycle is not None:
        _safe_transition(lifecycle, "waiting_for_tool")


def mark_tool_running() -> None:
    lifecycle = current_lifecycle()
    if lifecycle is not None:
        _safe_transition(lifecycle, "resume")


def _safe_transition(lifecycle: AgentLifecycle, method: str) -> None:
    try:
        snapshot = getattr(lifecycle, method)()
    except InvalidLifecycleTransition:
        return
    _emit_lifecycle_events(snapshot)
    callback = _CURRENT_CALLBACK.get()
    if callback is not None:
        try:
            callback(snapshot)
        except Exception:
            pass


def _emit_lifecycle_events(snapshot: LifecycleSnapshot) -> None:
    fields = {"status": snapshot.status.value, "updated_at": snapshot.updated_at}
    try:
        log_event("agent.lifecycle.changed", **fields)
        event_name = _LIFECYCLE_EVENTS.get(snapshot.status.value)
        if event_name is not None:
            log_event(event_name, **fields)
    except Exception:
        pass
