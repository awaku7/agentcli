from __future__ import annotations

import asyncio
from contextlib import contextmanager
from collections.abc import Iterator

from .lifecycle import AgentLifecycle, InvalidLifecycleTransition


@contextmanager
def lifecycle_execution(
    lifecycle: AgentLifecycle | None = None,
    *,
    cancel_exceptions: tuple[type[BaseException], ...] = (),
) -> Iterator[AgentLifecycle]:
    """Track one synchronous Agent execution with a shared lifecycle.

    The context manager deliberately treats cancellation-like exceptions as a
    cancelled execution and all other exceptions as failures. Invalid terminal
    transitions are ignored so a concurrent cancellation remains authoritative.
    """
    current = lifecycle or AgentLifecycle()
    _safe_transition(current, "start")
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


def _safe_transition(lifecycle: AgentLifecycle, method: str) -> None:
    try:
        getattr(lifecycle, method)()
    except InvalidLifecycleTransition:
        pass
