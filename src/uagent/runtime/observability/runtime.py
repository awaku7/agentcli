"""Runtime helpers that bridge UAG lifecycle boundaries to observability spans."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

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
    tool_name: str = ""
    content_buffer: Any = None
    next_content_ordinal: int = 1
    failed: bool = False


_PENDING_TOOL_SPAN: ContextVar[_PendingToolSpan | None] = ContextVar(
    "uagent_pending_tool_observability_span", default=None
)
_ACTIVE_TOOL_SPANS: ContextVar[tuple[_ActiveToolSpan, ...]] = ContextVar(
    "uagent_active_tool_observability_spans", default=()
)


@contextmanager
def fallback_chat_span(
    *,
    provider: str,
    model: str,
    request_input: Any,
    core: Any,
) -> Iterator[ObservabilitySpan]:
    """Trace one legacy/OpenAI-compatible LLM call at its shared fallback boundary.

    Registry-backed rounds own their canonical span in ``RoundOrchestrator``.
    The compatibility paths use this helper so supported providers that are not
    registry-backed still emit exactly one ``chat`` span. Responses usage stored
    on the legacy core is a standalone per-response snapshot, not a cumulative
    counter; when the provider replaces that snapshot, its values are therefore
    exported directly rather than subtracted from the previous response.
    """

    backend = get_observability_backend()
    attributes = {
        "uag.llm.provider": str(provider or "").strip(),
        "uag.llm.model": str(model or "").strip(),
    }
    usage_before_raw = getattr(core, "_last_responses_usage", None)
    with backend.start_span("chat", attributes=attributes) as span:
        if backend.enabled:
            try:
                from ..context_tokens import estimate_tokens

                span.set_attribute(
                    "uag.tokens.estimate.input",
                    estimate_tokens(
                        request_input,
                        provider=str(provider or ""),
                        model=str(model or ""),
                    ),
                )
            except Exception:
                pass
        try:
            yield span
        finally:
            if backend.enabled:
                try:
                    usage_after_raw = getattr(core, "_last_responses_usage", None)
                    if (
                        isinstance(usage_after_raw, Mapping)
                        and usage_after_raw
                        and usage_after_raw is not usage_before_raw
                    ):
                        reported_names = {
                            "input_tokens": "uag.tokens.reported.input",
                            "output_tokens": "uag.tokens.reported.output",
                            "total_tokens": "uag.tokens.reported.total",
                        }
                        for key, attribute_name in reported_names.items():
                            value = usage_after_raw.get(key)
                            if isinstance(value, (int, float)) and not isinstance(
                                value, bool
                            ):
                                span.set_attribute(attribute_name, max(0, int(value)))
                except Exception:
                    pass


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


def _new_tool_content_buffer() -> Any:
    try:
        from .content_capture import ContentCapturePolicy
        from .settings import get_observability_settings
        from .tool_content_capture import ToolContentCaptureBuffer

        policy = ContentCapturePolicy.from_settings(get_observability_settings())
        if not policy.enabled:
            return None
        return ToolContentCaptureBuffer(policy)
    except Exception:
        return None


def start_pending_tool_span() -> None:
    """Start one logical execute_tool span at the centralized runner boundary."""

    pending = _PENDING_TOOL_SPAN.get()
    _PENDING_TOOL_SPAN.set(None)
    backend = get_observability_backend()
    if not backend.enabled:
        return
    attributes: dict[str, Any] = {}
    tool_name = ""
    if pending is not None:
        tool_name = pending.name
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
    _ACTIVE_TOOL_SPANS.set(
        (
            *active_stack,
            _ActiveToolSpan(
                manager=manager,
                span=span,
                tool_name=tool_name,
                content_buffer=_new_tool_content_buffer(),
            ),
        )
    )


def _capture_trusted_tool_content(
    *,
    tool_name: str,
    category: str,
    value: object,
) -> bool:
    active_stack = _ACTIVE_TOOL_SPANS.get()
    if not active_stack:
        return False
    active = active_stack[-1]
    if (
        type(tool_name) is not str
        or not active.tool_name
        or active.tool_name != tool_name
        or active.content_buffer is None
        or active.next_content_ordinal > 32
    ):
        return False
    try:
        from .tool_content_capture import make_tool_candidate

        candidate = make_tool_candidate(
            tool_name=tool_name,
            category=category,
            value=value,
            ordinal=active.next_content_ordinal,
        )
        if candidate is None:
            return False
        if not active.content_buffer.admit(candidate):
            return False
        active.next_content_ordinal += 1
        return True
    except Exception:
        return False


def capture_trusted_tool_arguments(tool_name: str, args: object) -> bool:
    """Submit reviewed tool arguments to the owning ``execute_tool`` span."""

    return _capture_trusted_tool_content(
        tool_name=tool_name,
        category="tool_arguments",
        value=args,
    )


def capture_trusted_tool_result(tool_name: str, result: object) -> bool:
    """Submit a reviewed successful tool result to the owning tool span."""

    return _capture_trusted_tool_content(
        tool_name=tool_name,
        category="tool_result",
        value=result,
    )


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
        if active.content_buffer is not None:
            active.content_buffer.emit_to(active.span)
    except Exception:
        pass
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
    "capture_trusted_tool_arguments",
    "capture_trusted_tool_result",
    "fallback_chat_span",
    "start_pending_tool_span",
]
