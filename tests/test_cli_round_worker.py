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
        interrupt_lock=threading.Lock(),
        interrupt_requested=False,
        auto_pilot_exit_lock=threading.Lock(),
        auto_pilot_exit_requested=False,
        human_ask_queue=None,
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


def test_auto_unload_state_persists_across_worker_turns():
    # Regression: the auto-unload counters are lazily created inside
    # run_llm_rounds; bound only inside a worker's copied context they
    # would be discarded with it and restart empty on the next turn.
    from uagent import uagent_llm

    core = _fake_core()
    # The owner binding adopts the ambient context state on first
    # sight, which other tests in the same process may already have
    # populated; assert carry-over of this test's own marker and the
    # round counter's advance, not a pristine state.
    seen: list[tuple[object, object, int]] = []

    def _fn() -> None:
        state = uagent_llm._auto_unload_state()
        seen.append((state, state.last_round.get("tool_a"), state.total_rounds))
        state.last_round["tool_a"] = 1
        state.total_rounds += 1

    run_turn_on_worker(core, _fn, channel=dc.DisplayChannel())
    run_turn_on_worker(core, _fn, channel=dc.DisplayChannel())
    assert seen[0][0] is seen[1][0]
    assert seen[1][1] == 1
    assert seen[1][2] == seen[0][2] + 1


def test_loop_guard_state_survives_the_auto_pilot_handoff():
    # Regression: the initial turn begins a fresh loop-guard state
    # inside its worker; the auto-pilot continuation runs in a second
    # worker and passes preserve_tool_loop_state=True, so it must read
    # the state the first worker left on the session owner, not an
    # empty one.
    from uagent import llm_loop_guards as guards

    core = _fake_core()
    seen: list[object] = []

    def _initial_turn() -> None:
        state = guards.begin_loop_guard_turn()
        state.fingerprints["tool:example"] = 3
        state.consecutive.update({"name": "example", "count": 2})
        seen.append(state)

    def _continuation() -> None:
        seen.append(guards._loop_guard_state())

    run_turn_on_worker(core, _initial_turn, channel=dc.DisplayChannel())
    run_turn_on_worker(core, _continuation, channel=dc.DisplayChannel())
    assert seen[0] is seen[1]
    assert seen[1].fingerprints["tool:example"] == 3
    assert seen[1].consecutive["count"] == 2


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT delivery differs")
def test_ctrl_c_cancels_a_pending_human_ask():
    # Regression: a human_ask wait blocks on its answer queue, which
    # the interrupt flags do not reach; Ctrl+C must deliver the same
    # "cancel" the prompt itself accepts, or the CLI stays stuck until
    # the ask timeout (300s by default).
    import queue as queue_mod

    core = _fake_core()
    ask_queue: "queue_mod.Queue[str]" = queue_mod.Queue()
    core.human_ask_queue = ask_queue
    started = threading.Event()
    replies: list[str] = []

    def _fn() -> str:
        started.set()
        try:
            reply = ask_queue.get(timeout=5.0)
        except queue_mod.Empty:
            reply = ""
        replies.append(reply)
        return "ask done"

    def _send_sigint() -> None:
        started.wait(timeout=5.0)
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    sender = threading.Thread(target=_send_sigint, daemon=True)
    sender.start()
    with pytest.raises(KeyboardInterrupt):
        run_turn_on_worker(core, _fn, channel=dc.DisplayChannel())
    sender.join(timeout=5.0)
    assert replies == ["cancel"]


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT delivery differs")
def test_ctrl_c_sets_interrupt_flag_and_reraises():
    core = _fake_core()
    started = threading.Event()
    completed: list[str] = []

    def _fn() -> str:
        started.set()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            with core.interrupt_lock:
                if core.interrupt_requested:
                    completed.append("wound down")
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
    # Auto-pilot consumes interrupt_requested per round, so Ctrl+C must
    # also raise its exit request (the F12 monitor sets both).
    with core.auto_pilot_exit_lock:
        assert core.auto_pilot_exit_requested is True
    # Regression (CPython 3.11): an interrupted Thread.join can report
    # the worker stopped while it still runs. The wrapper must only
    # re-raise after the worker has actually wound down, which the
    # completion event (not join bookkeeping) guarantees.
    assert completed == ["wound down"]
