"""Host adapter helpers for binding Memory V3 turn identity.

V3-1 keeps authentication behavior unchanged while making the actor/workspace
boundary explicit around each host-triggered operation. Host adapters provide
only their runtime coordinates; identity selection remains centralized in
``identity_context``.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

from .identity_context import TurnContext, bind_turn_context, resolve_turn_context
from .session_store import project_id_from_path

_T = TypeVar("_T")


@contextmanager
def resolved_turn_context(
    *,
    entry_point: str,
    room_id: str = "",
    project_path: str = "",
    session_id: str = "",
    request_context: Any = None,
) -> Iterator[TurnContext]:
    """Resolve and bind one immutable turn context for a host operation."""

    path = str(project_path or "").strip() or os.getcwd()
    identity, turn = resolve_turn_context(
        entry_point=entry_point,
        room_id=room_id,
        project_id=project_id_from_path(path),
        session_id=session_id,
        request_context=request_context,
    )
    with bind_turn_context(turn, identity_context=identity):
        try:
            from .execution import apply_turn_context_to_current_agent_span

            apply_turn_context_to_current_agent_span(turn)
        except Exception:
            pass
        yield turn


def call_with_resolved_turn_context(
    fn: Callable[..., _T],
    *args: Any,
    entry_point: str,
    room_id: str = "",
    project_path: str = "",
    session_id: str = "",
    request_context: Any = None,
    **kwargs: Any,
) -> _T:
    """Resolve and bind one immutable turn context around ``fn``.

    The helper is intentionally host-neutral. CLI/GUI/A2A normally pass the
    current working directory, while Web passes the room base directory. The
    configured identity mode is resolved once for this call and never falls
    back to another mode after resolution failure.
    """

    with resolved_turn_context(
        entry_point=entry_point,
        room_id=room_id,
        project_path=project_path,
        session_id=session_id,
        request_context=request_context,
    ):
        return fn(*args, **kwargs)


__all__ = ["call_with_resolved_turn_context", "resolved_turn_context"]
