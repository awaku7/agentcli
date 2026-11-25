"""discord_channel send_and_wait: the reply wait observes interrupts."""

from __future__ import annotations

import json
import threading
import time

import pytest

from uagent import core
from uagent.tools import discord_channel_tool as mod
from uagent.tools.context import ToolCallbacks, init_callbacks


@pytest.fixture(autouse=True)
def _reset_interrupt_flag():
    with core.interrupt_lock:
        core.interrupt_requested = False
    yield
    with core.interrupt_lock:
        core.interrupt_requested = False


def _set_interrupt_flag() -> None:
    with core.interrupt_lock:
        core.interrupt_requested = True


def test_send_and_wait_stops_on_interrupt(monkeypatch):
    init_callbacks(ToolCallbacks())
    monkeypatch.setattr(mod, "_get_token", lambda args: "token")
    monkeypatch.setattr(
        mod, "_request_json", lambda *a, **k: {"id": "100", "content": "hi"}
    )
    monkeypatch.setattr(mod, "_get_self_user_id", lambda token: "self")
    monkeypatch.setattr(mod, "_fetch_recent_messages", lambda *a, **k: [])

    timer = threading.Timer(0.4, _set_interrupt_flag)
    started = time.monotonic()
    timer.start()
    try:
        out = mod.run_tool(
            {
                "action": "send_and_wait",
                "channel_id": "123",
                "message": "hello",
                "wait_s": 60,
                "poll_interval_s": 1,
            }
        )
    finally:
        timer.cancel()
    elapsed = time.monotonic() - started
    payload = json.loads(out)
    assert payload["interrupted"] is True
    assert payload["replies"] == []
    assert elapsed < 20.0
