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
    try:
        log_event(
            "agent.lifecycle.changed",
            status=snapshot.status.value,
            updated_at=snapshot.updated_at,
        )
    except Exception:
        pass
    callback = _CURRENT_CALLBACK.get()
    if callback is not None:
        try:
            callback(snapshot)
        except Exception:
            pass
