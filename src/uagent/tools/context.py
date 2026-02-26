"""tools.context

A "callback-injection" context to reduce dependency from tool implementations to the host (scheck_core / scheck.py).

- tools/__init__.py does not import scheck_core.
- Instead, the host (scheck.py) calls init_callbacks(...) at startup to inject necessary functions and accessors for shared state.

This module acts as a common gateway for all tools under the tools/ directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class ToolCallbacks:
    # Busy/Idle status updates
    set_status: Optional[Callable[[bool, str], None]] = None

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
    multi_input_sentinel: str = '"""end'

    # Event injection (e.g., timers)
    event_queue: Any = None

    # Display environment
    is_gui: bool = False

    # Settings
    cmd_encoding: str = "utf-8"
    cmd_exec_timeout_ms: int = 60_000
    python_exec_timeout_ms: int = 60_000
    url_fetch_timeout_ms: int = 60_000
    url_fetch_max_bytes: int = 1_000_000
    read_file_max_bytes: int = 1_000_000


_CALLBACKS: ToolCallbacks = ToolCallbacks()


def init_callbacks(cb: ToolCallbacks) -> None:
    global _CALLBACKS
    _CALLBACKS = cb


def get_callbacks() -> ToolCallbacks:
    return _CALLBACKS
