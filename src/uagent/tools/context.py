"""tools.context

A "callback-injection" context to reduce dependency from tool implementations to the host (scheck_core / scheck.py).

- tools/__init__.py does not import scheck_core.
- Instead, the host (scheck.py) calls init_callbacks(...) at startup to inject necessary functions and accessors for shared state.

This module acts as a common gateway for all tools under the tools/ directory.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..runtime.subagent_context import (
    get_active_sub_agent_name,
    reset_active_sub_agent_name,
    set_active_sub_agent_name,
)


@dataclass
class ToolCallbacks:
    # Busy/Idle status updates
    set_status: Optional[Callable[[bool, str], None]] = None
    debug: Optional[Callable[[str], None]] = None
    log: Optional[Callable[[str], None]] = None
    error: Optional[Callable[[str], None]] = None
    exception: Optional[Callable[[str], None]] = None
    finish_skill: Optional[Callable[[str], str]] = None
    rewrite_current_log_from_messages: Optional[Callable[[Any], str]] = None
    log_message: Optional[Callable[[dict[str, Any]], None]] = None
    image_event: Optional[Callable[[dict[str, Any]], None]] = None
    prompt_history_append: Optional[Callable[[str], None]] = None

    # Environment variable access
    get_env: Optional[Callable[[str], str]] = None
    get_env_url: Optional[Callable[[str, Optional[str]], str]] = None

    # Output truncation
    truncate_output: Optional[Callable[[str, str, int], str]] = None

    # Shared state for human_ask (synchronized with stdin_loop)
    human_ask_lock: Any = None
    human_ask_active_ref: Optional[Callable[[], bool]] = None
    human_ask_set_active: Optional[Callable[[bool], None]] = None
    human_ask_queue_ref: Optional[Callable[[], Any]] = None
    human_ask_set_queue: Optional[Callable[[Any], None]] = None
    human_ask_lines_ref: Optional[Callable[[], Any]] = None
    human_ask_multiline_active_ref: Optional[Callable[[], bool]] = None
    human_ask_set_multiline_active: Optional[Callable[[bool], None]] = None
    human_ask_set_password: Optional[Callable[[bool], None]] = None

    # Auto-pilot mode detection
    is_auto_pilot_active: Optional[Callable[[], bool]] = None
    is_cancelled: Optional[Callable[[], bool]] = None
    request_generation: Optional[Callable[[], object]] = None

    # Event injection (e.g., timers)
    event_queue: Any = None
    session_id: str | None = None
    session_store: Any = None

    # Display environment
    is_gui: bool = False

    # Settings
    cmd_encoding: str = "utf-8"
    cmd_exec_timeout_ms: int = 60_000
    python_exec_timeout_ms: int = 60_000
    url_fetch_timeout_ms: int = 60_000
    url_fetch_max_bytes: int = 1_000_000
    read_file_max_bytes: int = 1_000_000


@dataclass
class _ActiveSubAgentToken:
    context_token: Any
    span_manager: Any = None
    span: Any = None


def set_active_sub_agent(
    name: str | None,
    *,
    observability_name: str | None = None,
):
    """Bind the active sub-agent and optionally open its canonical child span.

    ``observability_name`` must already be a bounded, trusted metadata value.
    Arbitrary tool arguments are never used as remote span attributes by this
    generic context helper.
    """

    normalized = str(name) if name else None
    context_token = set_active_sub_agent_name(normalized)
    span_manager = None
    span = None

    if observability_name:
        try:
            from ..runtime.observability.bootstrap import get_observability_backend

            backend = get_observability_backend()
            span_manager = backend.start_span(
                "invoke_agent",
                attributes={"uag.agent.name": observability_name},
            )
            span = span_manager.__enter__()
        except Exception:
            span_manager = None
            span = None

    return _ActiveSubAgentToken(
        context_token=context_token,
        span_manager=span_manager,
        span=span,
    )


def reset_active_sub_agent(token: Any) -> None:
    """Close the active sub-agent span and restore the prior context.

    Observability is best-effort only. Any tracing failure is isolated from the
    sub-agent result, and older plain ContextVar tokens remain accepted for
    compatibility with callers across hot reloads.
    """

    if hasattr(token, "context_token") and hasattr(token, "span_manager"):
        try:
            span_manager = getattr(token, "span_manager", None)
            span = getattr(token, "span", None)
            if span_manager is not None:
                exc_type, exc, traceback = sys.exc_info()
                if exc_type is None and span is not None:
                    try:
                        span.set_status("ok")
                    except Exception:
                        pass
                try:
                    span_manager.__exit__(exc_type, exc, traceback)
                except Exception:
                    pass
        finally:
            reset_active_sub_agent_name(token.context_token)
        return

    reset_active_sub_agent_name(token)


def get_active_sub_agent() -> str | None:
    return get_active_sub_agent_name()


# Preserve injected host callbacks across hot-reloads.  ``system_reload`` reloads
# tool modules in place; recreating this object would silently disconnect the CLI
# from human_ask and other host-dependent tools.
_CALLBACKS: ToolCallbacks = globals().get("_CALLBACKS", ToolCallbacks())


def init_callbacks(cb: ToolCallbacks) -> None:
    global _CALLBACKS
    _CALLBACKS = cb


def get_callbacks() -> ToolCallbacks:
    return _CALLBACKS
