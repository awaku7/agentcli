"""Runtime helpers that bridge UAG lifecycle boundaries to observability spans."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Mapping

from .api import ObservabilitySpan
from .bootstrap import get_observability_backend


@dataclass(frozen=True)
class _PendingToolSpan:
    name: str
    side_effect: str = ""


@dataclass
class _ActiveToolSpan:
    manager: Any
    span: ObservabilitySpan
    failed: bool = False


_PENDING_TOOL_SPAN: ContextVar[_PendingToolSpan | None] = ContextVar(
    "uagent_pending_tool_observability_span", default=None
)
_ACTIVE_TOOL_SPANS: ContextVar[tuple[_ActiveToolSpan, ...]] = ContextVar(
    "uagent_active_tool_observability_spans", default=()
)


def before_structured_event(event_code: str, fields: Mapping[str, Any]) -> None:
    """Update span state before a structured event is serialized.

    Tool dispatch is recorded before confirmation/execution. We retain only safe
    metadata there and start the actual tool span later at the centralized
    lifecycle boundary, so denied confirmations never create execution spans.
    """

    if event_code == "tool.dispatch":
        _PENDING_TOOL_SPAN.set(
            _PendingToolSpan(
                name=str(fields.get("tool") or "").strip(),
                side_effect=str(fields.get("side_effect") or "").strip(),
            )
        )
        return

    active_stack = _ACTIVE_TOOL_SPANS.get()
    if not active_stack:
        return
    active = active_stack[-1]
    if event_code == "tool.failed":
        active.failed = True
        active.span.set_attribute("uag.status", "error")
        error_type = str(fields.get("error_type") or "").strip()
        if error_type:
            active.span.set_attribute("uag.error.type", error_type)
        active.span.set_status("error", error_type or None)
        active.span.add_event("tool.failed")
    elif event_code == "tool.completed":
        active.span.set_attribute("uag.status", "ok")
        active.span.set_status("ok")
        active.span.add_event("tool.completed")


def after_structured_event(event_code: str) -> None:
    """Close tool spans only after terminal log correlation has been emitted."""

    if event_code not in {"tool.completed", "tool.failed"}:
        return
    _finish_active_tool_span()


def start_pending_tool_span() -> None:
    """Start one logical execute_tool span at the centralized runner boundary."""

    pending = _PENDING_TOOL_SPAN.get()
    _PENDING_TOOL_SPAN.set(None)
    backend = get_observability_backend()
    if not backend.enabled:
        return
    attributes: dict[str, Any] = {}
    if pending is not None:
        if pending.name:
            attributes["uag.tool.name"] = pending.name
        if pending.side_effect:
            attributes["uag.tool.side_effect"] = pending.side_effect
    try:
        manager = backend.start_span("execute_tool", attributes=attributes)
        span = manager.__enter__()
    except Exception:
        return
    active_stack = _ACTIVE_TOOL_SPANS.get()
    _ACTIVE_TOOL_SPANS.set((*active_stack, _ActiveToolSpan(manager=manager, span=span)))


def abandon_active_tool_span() -> None:
    """Best-effort cleanup for an unexpected runner path with no terminal event."""

    active_stack = _ACTIVE_TOOL_SPANS.get()
    if not active_stack:
        return
    active = active_stack[-1]
    active.failed = True
    active.span.set_attribute("uag.status", "abandoned")
    active.span.set_status("error", "tool span abandoned")
    _finish_active_tool_span()


def _finish_active_tool_span() -> None:
    active_stack = _ACTIVE_TOOL_SPANS.get()
    if not active_stack:
        return
    active = active_stack[-1]
    _ACTIVE_TOOL_SPANS.set(active_stack[:-1])
    try:
        active.manager.__exit__(None, None, None)
    except Exception:
        pass


def _reset_runtime_observability_for_tests() -> None:
    _PENDING_TOOL_SPAN.set(None)
    while _ACTIVE_TOOL_SPANS.get():
        _finish_active_tool_span()


__all__ = [
    "abandon_active_tool_span",
    "after_structured_event",
    "before_structured_event",
    "start_pending_tool_span",
]
