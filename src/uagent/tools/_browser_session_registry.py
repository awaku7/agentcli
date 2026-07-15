# Persistent browser session registry (reload-safe).
# Kept in a private module so importlib.reload of browser_playwright_tool
# does not wipe live sessions.
from __future__ import annotations

import atexit
import threading
from typing import Any, Callable

_SESSIONS: dict[str, Any] = {}
_SESSIONS_LOCK = threading.RLock()
_ATEXIT_REGISTERED = False
_ATEXIT_HOOK: Callable[[], None] | None = None


def get_sessions() -> dict[str, Any]:
    return _SESSIONS


def get_lock() -> threading.RLock:
    return _SESSIONS_LOCK


def is_atexit_registered() -> bool:
    return _ATEXIT_REGISTERED


def register_atexit(hook: Callable[[], None]) -> None:
    """Register process-exit cleanup once. Replaces hook if already registered."""
    global _ATEXIT_REGISTERED, _ATEXIT_HOOK
    _ATEXIT_HOOK = hook
    if not _ATEXIT_REGISTERED:

        def _runner() -> None:
            if _ATEXIT_HOOK is not None:
                try:
                    _ATEXIT_HOOK()
                except Exception:
                    pass

        atexit.register(_runner)
        _ATEXIT_REGISTERED = True
