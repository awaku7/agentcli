"""Shared host-side confirmation path for risky built-in tool operations.

Tool argument flags never count as approval. Only the common dispatcher may
bind an already granted approval for the active tool call.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_ACTIVE_TOOL: ContextVar[tuple[str, bool] | None] = ContextVar(
    "uagent_active_tool_confirmation", default=None
)


@contextmanager
def dispatched_tool(name: str, *, approved: bool) -> Iterator[None]:
    token = _ACTIVE_TOOL.set((name, bool(approved)))
    try:
        yield
    finally:
        _ACTIVE_TOOL.reset(token)


def active_tool_name() -> str | None:
    current = _ACTIVE_TOOL.get()
    return current[0] if current is not None else None


def dispatcher_approved(name: str) -> bool:
    current = _ACTIVE_TOOL.get()
    return bool(current and current[0] == name and current[1])


def confirm_operation(message: str, *, tool_name: str) -> bool:
    """Use the host's same ToolPolicy -> human_ask confirmation callback.

    No raw input() fallback: unavailable/cancelled interaction denies operation.
    Tool-specific text remains localized by the caller's existing translator.
    """
    if dispatcher_approved(tool_name):
        return True

    from . import get_confirmation_callback
    from .tool_policy import (
        SideEffect,
        ToolPolicy,
        default_confirmation_callback,
    )

    callback = get_confirmation_callback() or default_confirmation_callback
    policy = ToolPolicy(side_effect=SideEffect.DESTRUCTIVE, requires_confirmation=True)
    try:
        return bool(callback(tool_name, {"details": message}, policy))
    except Exception:
        return False
