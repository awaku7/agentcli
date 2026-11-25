"""CLI round worker thread (single-writer stage 2a)."""

from __future__ import annotations

import contextvars
import os
import signal
import sys
import threading
import time
import types

import pytest

from uagent.cli_impl.main import run_turn_on_worker
from uagent.runtime import display_channel as dc


def _fake_core() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        interrupt_lock=threading.Lock(), interrupt_requested=False
    )


def test_result_passes_through_and_runs_on_a_worker_thread():
    core = _fake_core()
    seen: dict[str, object] = {}

    def _fn(value: int) -> int:
        seen["thread"] = threading.current_thread().name
        return value + 1

    assert run_turn_on_worker(core, _fn, 41, channel=dc.DisplayChannel()) == 42
    assert seen["thread"] == "uagent-cli-round"


def test_turn_core_keyword_reaches_the_wrapped_function():
    # Regression: the production call sites pass core=core to the turn
    # function; the wrapper must not consume that keyword itself.
    core = _fake_core()
    marker = object()

    def _fn(provider: str, core: object = None) -> object:
        return core

    result = run_turn_on_worker(
        core, _fn, "prov", core=marker, channel=dc.DisplayChannel()
    )
    assert result is marker


def test_exception_is_reraised_on_the_waiting_thread():
    core = _fake_core()

    def _fn() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        run_turn_on_worker(core, _fn, channel=dc.DisplayChannel())


def test_worker_inherits_context_and_relay_binding():
    core = _fake_core()
    channel = dc.DisplayChannel()
    marker: contextvars.ContextVar[str] = contextvars.ContextVar("test_marker")
    token = marker.set("inherited")
    seen: dict[str, object] = {}

    def _fn() -> None:
        seen["marker"] = marker.get()
        seen["relay"] = dc.stream_relay()

    try:
        run_turn_on_worker(core, _fn, channel=channel)
    finally:
        marker.reset(token)
    assert seen["marker"] == "inherited"
    assert seen["relay"] is channel
    assert dc.stream_relay() is None


def test_worker_returns_only_after_relayed_stream_drains():
    core = _fake_core()
    channel = dc.DisplayChannel()
    rendered: list[str] = []
    stop = threading.Event()

    def _render() -> None:
        while not stop.is_set():
            event = channel.take(timeout=0.05)
            if isinstance(event, dc.StreamDelta):
                time.sleep(0.02)
                rendered.append(event.text)
                channel.note_stream_rendered()

    renderer = threading.Thread(target=_render, daemon=True)
    renderer.start()

    def _fn() -> str:
        relay = dc.stream_relay()
        assert relay is not None
        for i in range(5):
            relay.post_stream(dc.StreamDelta(text=f"d{i}"))
        return "done"

    try:
        assert run_turn_on_worker(core, _fn, channel=channel) == "done"
        assert rendered == [f"d{i}" for i in range(5)]
    finally:
        stop.set()
        renderer.join(timeout=5.0)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT delivery differs")
def test_ctrl_c_sets_interrupt_flag_and_reraises():
    core = _fake_core()
    started = threading.Event()

    def _fn() -> str:
        started.set()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            with core.interrupt_lock:
                if core.interrupt_requested:
                    return "wound down"
            time.sleep(0.01)
        return "never interrupted"

    def _send_sigint() -> None:
        started.wait(timeout=5.0)
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    sender = threading.Thread(target=_send_sigint, daemon=True)
    sender.start()
    with pytest.raises(KeyboardInterrupt):
        run_turn_on_worker(core, _fn, channel=dc.DisplayChannel())
    sender.join(timeout=5.0)
    with core.interrupt_lock:
        assert core.interrupt_requested is True
