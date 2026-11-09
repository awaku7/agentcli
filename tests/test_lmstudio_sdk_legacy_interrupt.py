"""Stop must silence abandoned LM Studio native SDK stream workers."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from uagent import core as core_module
from uagent.llm_helpers import LLMWaitInterrupted, _call_maybe_thread
from uagent.runtime.legacy_lmstudio_sdk_stream import collect_lmstudio_sdk_stream


def _chunk(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
    )


def test_lmstudio_sdk_stream_stops_on_host_interrupt_without_end_event(
    monkeypatch,
) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    messages: list[dict] = []
    core = SimpleNamespace(
        _is_web=True,
        interrupt_requested=False,
        log_message=messages.append,
    )

    def stream():
        yield _chunk("before")
        core.interrupt_requested = True
        yield _chunk("after")
        yield SimpleNamespace(choices=[], usage={"prompt_tokens": 10})

    with pytest.raises(LLMWaitInterrupted, match="interrupted"):
        collect_lmstudio_sdk_stream(stream(), core=core)

    assert messages == [{"type": "assistant_stream_delta", "delta": "before"}]


def test_lmstudio_sdk_abandoned_worker_stays_silent_after_stop_reset(
    monkeypatch,
) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    rendered: list[dict] = []
    ready = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    suppressed: list[bool] = []
    core = SimpleNamespace(_is_web=True, log_message=rendered.append)

    def stream():
        yield _chunk("before")
        ready.set()
        if not release.wait(4):
            raise AssertionError("test worker was never released")
        yield _chunk("after")
        yield SimpleNamespace(
            choices=[],
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )

    def worker():
        try:
            collect_lmstudio_sdk_stream(stream(), core=core)
        except LLMWaitInterrupted:
            suppressed.append(True)
        finally:
            finished.set()

    def stop():
        if ready.wait(4):
            with core_module.interrupt_lock:
                core_module.interrupt_requested = True

    stopper = threading.Thread(target=stop, daemon=True)
    stopper.start()
    try:
        with pytest.raises(LLMWaitInterrupted, match="interrupt requested"):
            _call_maybe_thread(worker, use_llm_thread=True)
        # A new request resets the shared interrupt flag before the old
        # in-flight SDK network iterator produces its next chunk.
        with core_module.interrupt_lock:
            core_module.interrupt_requested = False
    finally:
        release.set()
        stopper.join(timeout=4)
        with core_module.interrupt_lock:
            core_module.interrupt_requested = False

    assert finished.wait(4)
    assert suppressed == [True]
    assert rendered == [{"type": "assistant_stream_delta", "delta": "before"}]


def test_lmstudio_sdk_ctrl_c_abandons_worker_even_without_stop_flag(
    monkeypatch,
) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    rendered: list[dict] = []
    ready = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    suppressed: list[bool] = []
    core = SimpleNamespace(_is_web=True, log_message=rendered.append)

    def stream():
        yield _chunk("before")
        ready.set()
        if not release.wait(4):
            raise AssertionError("test worker was never released")
        yield _chunk("after")

    def worker():
        try:
            collect_lmstudio_sdk_stream(stream(), core=core)
        except LLMWaitInterrupted:
            suppressed.append(True)
        finally:
            finished.set()

    original_join = threading.Thread.join

    def interrupt_join(thread, timeout=None):
        if thread.name == "uagent-llm-call":
            assert ready.wait(4)
            # Invoke the real join first, then reproduce CPython's SIGINT
            # behavior: is_alive can be false while this worker is blocked.
            original_join(thread, 0.01)
            monkeypatch.setattr(thread, "is_alive", lambda: False)
            raise KeyboardInterrupt("Ctrl-C")
        return original_join(thread, timeout)

    monkeypatch.setattr(threading.Thread, "join", interrupt_join)
    try:
        with pytest.raises(KeyboardInterrupt, match="Ctrl-C"):
            _call_maybe_thread(worker, use_llm_thread=True)
    finally:
        # Ctrl-C does not need to set the global Stop flag. The next request
        # can proceed while the old SDK network stream is still in flight.
        release.set()

    assert finished.wait(4)
    assert suppressed == [True]
    assert rendered == [{"type": "assistant_stream_delta", "delta": "before"}]
