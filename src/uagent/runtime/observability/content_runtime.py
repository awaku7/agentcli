"""Runtime binding for Phase 4A controlled-content capture."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

from .content_capture import (
    ContentCaptureBuffer,
    ContentCapturePolicy,
    make_text_candidate,
)
from .settings import ObservabilitySettings


@dataclass
class _AgentContentCaptureState:
    buffer: ContentCaptureBuffer
    next_ordinal: int = 1


_CURRENT_AGENT_CONTENT: ContextVar[_AgentContentCaptureState | None] = ContextVar(
    "uagent_current_agent_content_capture",
    default=None,
)


@contextmanager
def bind_agent_content_capture(
    span: object,
    settings: ObservabilitySettings,
) -> Iterator[None]:
    """Bind one controlled-content buffer to the current ``invoke_agent`` span.

    The buffer exists only while the canonical Agent span is active.  Events are
    emitted before that span closes and only through the dedicated trusted
    carrier exposed by the backend span.  Any observability failure is ignored.
    """

    policy = ContentCapturePolicy.from_settings(settings)
    if not policy.enabled:
        yield
        return

    state = _AgentContentCaptureState(ContentCaptureBuffer(policy))
    token = _CURRENT_AGENT_CONTENT.set(state)
    try:
        yield
    finally:
        try:
            _CURRENT_AGENT_CONTENT.reset(token)
        except Exception:
            pass
        try:
            state.buffer.emit_to(span)
        except Exception:
            pass


def capture_logged_message(message: object) -> bool:
    """Admit one reviewed plain-text message candidate for the active Agent span.

    Envelope metadata is inspected only to select the reviewed adapter.  The
    message content itself is handed to ``ContentCaptureBuffer`` without
    conversion or rendering so the existing fail-closed policy remains the sole
    authority for type checks, secret detection, bounds, rendering, and budget.
    """

    state = _CURRENT_AGENT_CONTENT.get()
    if state is None or type(message) is not dict:
        return False

    try:
        if message.get("_uagent_internal") or message.get("_uagent_ui_only"):
            return False
        role = message.get("role")
        if role == "user":
            category = "user_input"
        elif role == "assistant":
            category = "assistant_output"
        else:
            return False

        ordinal = state.next_ordinal
        state.next_ordinal += 1
        candidate = make_text_candidate(
            category=category,
            value=message.get("content"),  # type: ignore[arg-type]
            ordinal=ordinal,
        )
        return state.buffer.admit(candidate)
    except Exception:
        return False


__all__ = ["bind_agent_content_capture", "capture_logged_message"]
