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
    seen_messages: list[dict[str, object]] = field(default_factory=list)


_DISABLED = object()
_CURRENT_AGENT_CONTENT: ContextVar[object | None] = ContextVar(
    "uagent_current_agent_content_capture",
    default=None,
)
_PENDING_USER_MESSAGE: ContextVar[dict[str, object] | None] = ContextVar(
    "uagent_pending_agent_user_message",
    default=None,
)


def _eligible_envelope(message: object) -> tuple[str, str] | None:
    if type(message) is not dict:
        return None
    try:
        if message.get("_uagent_internal") or message.get("_uagent_ui_only"):
            return None
        if "attachments" in message:
            return None
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or type(content) is not str:
            return None
        return role, content
    except Exception:
        return None


def _admit_message(
    state: _AgentContentCaptureState,
    message: dict[str, object],
) -> bool:
    envelope = _eligible_envelope(message)
    if envelope is None:
        return False
    role, content = envelope
    if any(message is seen for seen in state.seen_messages) or state.next_ordinal > 32:
        return False
    state.seen_messages.append(message)
    ordinal = state.next_ordinal
    state.next_ordinal += 1
    category = "user_input" if role == "user" else "assistant_output"
    try:
        candidate = make_text_candidate(
            category=category,
            value=content,
            ordinal=ordinal,
        )
        return state.buffer.admit(candidate)
    except Exception:
        return False


@contextmanager
def bind_agent_content_capture(
    span: object,
    settings: ObservabilitySettings,
) -> Iterator[None]:
    """Bind one controlled-content buffer to the current ``invoke_agent`` span.

    A user message logged immediately before ``lifecycle_execution()`` is held
    only in the current ContextVar execution context and consumed once here.
    Disabled nested Agent scopes bind an explicit sentinel so they cannot leak
    content into an enabled parent span.
    """

    pending = _PENDING_USER_MESSAGE.get()
    _PENDING_USER_MESSAGE.set(None)

    try:
        policy = ContentCapturePolicy.from_settings(settings)
    except Exception:
        policy = None

    if policy is None or not policy.enabled:
        token = _CURRENT_AGENT_CONTENT.set(_DISABLED)
        try:
            yield
        finally:
            _CURRENT_AGENT_CONTENT.reset(token)
        return

    state = _AgentContentCaptureState(ContentCaptureBuffer(policy))
    token = _CURRENT_AGENT_CONTENT.set(state)
    try:
        if pending is not None:
            _admit_message(state, pending)
        yield
    finally:
        try:
            state.buffer.emit_to(span)
        except Exception:
            pass
        _CURRENT_AGENT_CONTENT.reset(token)


def discard_pending_user_message(message: object | None = None) -> bool:
    """Discard the staged pre-lifecycle user envelope, optionally by identity.

    Hosts call this when a submitted user turn is aborted before entering the
    owning Agent lifecycle. Supplying ``message`` makes the discard fail closed
    unless it is the exact object currently staged.
    """

    try:
        pending = _PENDING_USER_MESSAGE.get()
        if pending is None:
            return False
        if message is not None and pending is not message:
            return False
        _PENDING_USER_MESSAGE.set(None)
        return True
    except Exception:
        return False


def capture_logged_message(message: object) -> bool:
    """Capture one reviewed plain-text user/assistant logging envelope.

    Before an Agent span is active, only the latest eligible user envelope is
    retained for one subsequent Agent lifecycle. Once the Agent span is active,
    only assistant output is accepted from the logging boundary; user input must
    come from the pre-lifecycle staged envelope. This prevents tool-generated or
    other synthetic in-span user messages from being exported as operator input.
    A disabled nested scope suppresses both capture and pending-user staging.
    """

    envelope = _eligible_envelope(message)
    if envelope is None:
        return False
    role, _content = envelope
    state = _CURRENT_AGENT_CONTENT.get()

    if state is _DISABLED:
        return False
    if isinstance(state, _AgentContentCaptureState):
        if role != "assistant":
            return False
        return _admit_message(state, message)  # type: ignore[arg-type]

    if role != "user":
        return False
    try:
        _PENDING_USER_MESSAGE.set(message)  # type: ignore[arg-type]
        return True
    except Exception:
        return False


__all__ = [
    "bind_agent_content_capture",
    "capture_logged_message",
    "discard_pending_user_message",
]
