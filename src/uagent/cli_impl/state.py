"""Shared mutable state for the uagent CLI (split from cli.py)."""

from __future__ import annotations

import threading
from typing import Any

# Set before the main thread leaves so the daemon stdin thread can get out of
# prompt_toolkit/select/msvcrt waits before interpreter shutdown. Leaving that
# thread alive can make Python 3.14 print a traceback from subprocess' internal
# reader-thread cleanup while the process is exiting.
_CLI_SHUTDOWN = threading.Event()

_PROMPT_SESSION: Any = None
_PROMPT_REPLY_SESSION: Any = None
_PROMPT_HISTORY: list[str] = []
