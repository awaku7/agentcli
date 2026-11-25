"""modbus_monitor / echonet_monitor: interrupt-flag cancellation."""

from __future__ import annotations

import json
import threading
import time

import pytest

from uagent import core
from uagent.tools import echonet_monitor_tool, modbus_monitor_tool


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


def test_modbus_monitor_stops_on_interrupt():
    # Nothing answers on 127.0.0.1:502, so the monitor spends its time
    # in the between-poll sleep; the interrupt must cut the 60s
    # monitoring duration short instead of running to the deadline.
    timer = threading.Timer(0.6, _set_interrupt_flag)
    started = time.monotonic()
    timer.start()
    try:
        out = modbus_monitor_tool.run_tool(
            {
                "ip": "127.0.0.1",
                "port": 502,
                "duration": 60,
                "interval": 10,
                "timeout": 1,
            }
        )
    finally:
        timer.cancel()
    elapsed = time.monotonic() - started
    payload = json.loads(out)
    assert payload["stopped_reason"] == "interrupted"
    assert elapsed < 20.0


def test_echonet_monitor_stops_on_interrupt(monkeypatch):
    # No ECHONET node answers; each poll comes back empty and the
    # interrupt must stop the loop well before the 60s deadline. The
    # node query is stubbed: this environment cannot send UDP, and the
    # loop's cancellation is what is under test.
    monkeypatch.setattr(echonet_monitor_tool, "_query_node", lambda **_kwargs: [])
    timer = threading.Timer(0.6, _set_interrupt_flag)
    started = time.monotonic()
    timer.start()
    try:
        out = echonet_monitor_tool.run_tool(
            {"ip": "127.0.0.1", "duration": 60, "interval": 5, "timeout": 1}
        )
    finally:
        timer.cancel()
    elapsed = time.monotonic() - started
    payload = json.loads(out)
    assert payload["stopped_reason"] == "interrupted"
    assert elapsed < 20.0
