"""Asyncio event-loop helpers for tool implementations."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def windows_selector_event_loop_policy() -> Iterator[None]:
    """Temporarily use SelectorEventLoop on Windows for BLE stacks.

    Some BLE backends (notably bleak on Windows) work more reliably under
    ``WindowsSelectorEventLoopPolicy``.  Setting that policy process-wide
    without restoring it breaks tools that need subprocess support via
    ``ProactorEventLoop`` (for example Playwright).

    This context manager installs Selector only for the wrapped section and
    always restores the previous policy afterwards.
    """
    if sys.platform != "win32":
        yield
        return

    try:
        old_policy = asyncio.get_event_loop_policy()
    except Exception:
        old_policy = None

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        # Keep current policy if Selector cannot be installed.
        yield
        return

    try:
        yield
    finally:
        if old_policy is not None:
            try:
                asyncio.set_event_loop_policy(old_policy)
            except Exception:
                pass
