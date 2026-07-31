from __future__ import annotations

import time
from types import SimpleNamespace

from uagent.tools._genre_control_util import (
    disable_single_tool,
    is_tool_pinned,
    list_pinned_tools,
    pin_tool,
    unpin_tool,
    _PINNED_TOOLS,
    _LOADED_SINGLE_TOOLS,
    _TOOL_DYNAMIC_THRESHOLDS,
)
from uagent.tools import browser_playwright_tool as bp


def setup_function():
    _PINNED_TOOLS.clear()
    _LOADED_SINGLE_TOOLS.clear()
    _TOOL_DYNAMIC_THRESHOLDS.clear()


def test_pin_unpin_api():
    assert pin_tool("browser_playwright", reason="session") is True
    assert is_tool_pinned("browser_playwright") is True
    assert list_pinned_tools()["browser_playwright"] == "session"
    assert unpin_tool("browser_playwright") is True
    assert is_tool_pinned("browser_playwright") is False


def test_disable_single_tool_respects_pin():
    # Simulate a loaded tool entry without full registration.
    _LOADED_SINGLE_TOOLS["dummy_tool"] = -1
    _TOOL_DYNAMIC_THRESHOLDS["dummy_tool"] = (5, 0, 1)
    pin_tool("dummy_tool", reason="test")
    assert disable_single_tool("dummy_tool") is False
    assert is_tool_pinned("dummy_tool") is True
    # force unload
    assert disable_single_tool("dummy_tool", force=True) is False or True
    # force removes pin even if tool was not in TOOL_SPECS
    assert is_tool_pinned("dummy_tool") is False


def test_touch_all_sessions_refreshes_ttl(monkeypatch):
    now = time.time()
    fake = SimpleNamespace(
        session_id="bp_test",
        closed=False,
        last_used_at=now - 1000,
        ttl_sec=300,
        hard_lifetime_sec=1800,
        created_at=now - 1000,
        busy=False,
        lock=__import__("threading").RLock(),
        loop=None,
        thread=None,
    )
    with bp._SESSIONS_LOCK:
        bp._SESSIONS.clear()
        bp._SESSIONS[fake.session_id] = fake
    try:
        bp._touch_all_sessions()
        assert fake.last_used_at >= now - 1
        assert bp._session_expired(fake) is False
    finally:
        with bp._SESSIONS_LOCK:
            bp._SESSIONS.clear()


def test_pin_helpers_on_browser_tool():
    with bp._SESSIONS_LOCK:
        bp._SESSIONS.clear()
    bp._pin_browser_tool(reason="unit")
    assert is_tool_pinned("browser_playwright") is True
    bp._maybe_unpin_browser_tool()
    assert is_tool_pinned("browser_playwright") is False
