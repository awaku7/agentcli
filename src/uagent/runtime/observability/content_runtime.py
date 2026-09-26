"""Runtime binding for Phase 4A controlled-content capture."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
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
    seen_message_ids: set[int] = field(default_factory=set)


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

    The buffer exists only while the canonical Agent span is active. Events are
    emitted before that span closes and only through the dedicated trusted
    carrier exposed by the backend span. Any observability failure is ignored.
    """

    try:
        policy = ContentCapturePolicy.from_settings(settings)
    except Exception:
        yield
        return
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

    Envelope metadata is inspected only to select the reviewed adapter. The
    message content itself is handed to ``ContentCaptureBuffer`` without
    conversion or rendering so the existing fail-closed policy remains the sole
    authority for type checks, secret detection, bounds, rendering, and budget.
    The same exact message object is admitted at most once per Agent span.
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

        message_id = id(message)
        if message_id in state.seen_message_ids:
            return False
        state.seen_message_ids.add(message_id)

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


def capture_latest_user_message(messages: object) -> bool:
    """Capture only the most recent user envelope for the current LLM execution."""

    if type(messages) is not list:
        return False
    try:
        for message in reversed(messages):
            if type(message) is dict and message.get("role") == "user":
                return capture_logged_message(message)
    except Exception:
        return False
    return False


def capture_appended_messages(messages: object, start_index: int) -> int:
    """Capture reviewed envelopes appended during one LLM execution."""

    if type(messages) is not list or type(start_index) is not int:
        return 0
    if start_index < 0 or start_index > len(messages):
        return 0

    captured = 0
    try:
        for index in range(start_index, len(messages)):
            if capture_logged_message(messages[index]):
                captured += 1
    except Exception:
        return captured
    return captured


__all__ = [
    "bind_agent_content_capture",
    "capture_appended_messages",
    "capture_latest_user_message",
    "capture_logged_message",
]
