"""Shared mutable state for the uagent CLI (split from cli.py)."""

from __future__ import annotations

import threading
from typing import Any

# Set before the main thread leaves so the daemon stdin thread can get out of
# prompt_toolkit/select/msvcrt waits before interpreter shutdown. Leaving that
# thread alive can make Python 3.14 print a traceback from subprocess' internal
# reader-thread cleanup while the process is exiting.
_CLI_SHUTDOWN = threading.Event()

_TYPEAHEAD_LOCK = threading.Lock()
_TYPEAHEAD_PENDING = False


def reserve_typeahead_slot() -> bool:
    """Reserve the single CLI user-message slot that may wait behind a turn."""
    global _TYPEAHEAD_PENDING
    with _TYPEAHEAD_LOCK:
        if _TYPEAHEAD_PENDING:
            return False
        _TYPEAHEAD_PENDING = True
        return True


def release_typeahead_slot() -> None:
    """Release the queued user-message slot when the main loop picks it up."""
    global _TYPEAHEAD_PENDING
    with _TYPEAHEAD_LOCK:
        _TYPEAHEAD_PENDING = False


def reset_typeahead_slot() -> None:
    """Reset type-ahead state for a fresh CLI main-loop invocation."""
    release_typeahead_slot()


_PROMPT_SESSION: Any = None
_PROMPT_REPLY_SESSION: Any = None
_PROMPT_HISTORY: list[str] = []
