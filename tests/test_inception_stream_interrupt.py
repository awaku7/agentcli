"""Inception legacy streaming must stop abandoned worker output and usage."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from uagent import core as core_module
from uagent.llm_helpers import LLMWaitInterrupted, _call_maybe_thread
from uagent.runtime.inception_stream_compat import render_legacy_inception_stream


def _delta(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=[]))]
    )


def _usage() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[],
        usage={"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
    )


def test_inception_stream_stages_usage_for_owning_request(monkeypatch) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_is_web=False, _last_responses_usage=previous)
    collected: list[dict[str, int]] = []
    result = render_legacy_inception_stream(
        [_delta("answer"), _usage()],
        diffusing=False,
        print_delta_fn=lambda _: None,
        core=core,
        usage_sink=collected,
    )
    assert result[0] == "answer"
    assert collected == [{"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}]
    assert core._last_responses_usage is previous
    assert core._last_inception_stream_terminal == "ResponseCompleted"


def test_inception_host_stop_suppresses_later_deltas_and_end(monkeypatch) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    events: list[dict] = []
    core = SimpleNamespace(
        _is_web=True,
        interrupt_requested=False,
        log_message=events.append,
    )

    def stream():
        yield _delta("before")
        core.interrupt_requested = True
        yield _delta("after")
        yield _usage()

    with pytest.raises(LLMWaitInterrupted, match="interrupted"):
        render_legacy_inception_stream(
            stream(), diffusing=False, print_delta_fn=None, core=core
        )
    assert events == [{"type": "assistant_stream_delta", "delta": "before"}]


def test_abandoned_inception_worker_stays_silent_after_stop_reset(
    monkeypatch,
) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    events: list[dict] = []
    previous = {"input_tokens": 900, "output_tokens": 300}
    core = SimpleNamespace(
        _is_web=True,
        log_message=events.append,
        _last_responses_usage=previous,
    )
    measured: list[dict[str, int]] = []
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    suppressed: list[bool] = []

    def stream():
        yield _delta("before")
        started.set()
        if not release.wait(4):
            raise AssertionError("test stream was not released")
        yield _delta("after")
        yield _usage()

    def worker():
        try:
            render_legacy_inception_stream(
                stream(),
                diffusing=False,
                print_delta_fn=None,
                core=core,
                usage_sink=measured,
            )
        except LLMWaitInterrupted:
            suppressed.append(True)
        finally:
            finished.set()

    def stop():
        if started.wait(4):
            with core_module.interrupt_lock:
                core_module.interrupt_requested = True

    stopper = threading.Thread(target=stop, daemon=True)
    stopper.start()
    try:
        with pytest.raises(LLMWaitInterrupted, match="interrupt requested"):
            _call_maybe_thread(worker, use_llm_thread=True)
        with core_module.interrupt_lock:
            core_module.interrupt_requested = False
    finally:
        release.set()
        stopper.join(timeout=4)
        with core_module.interrupt_lock:
            core_module.interrupt_requested = False

    assert finished.wait(4)
    assert suppressed == [True]
    assert events == [{"type": "assistant_stream_delta", "delta": "before"}]
    assert core._last_responses_usage is previous
    assert measured == []


def test_inception_stop_before_first_event_closes_sdk_stream(monkeypatch) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)

    class UnstartedStream:
        def __init__(self) -> None:
            self.closed = False
            self.iterated = False

        def __iter__(self):
            self.iterated = True
            return iter(())

        def close(self) -> None:
            self.closed = True

    stream = UnstartedStream()
    core = SimpleNamespace(_is_web=True, interrupt_requested=True)
    with pytest.raises(LLMWaitInterrupted, match="interrupted"):
        render_legacy_inception_stream(
            stream, diffusing=False, print_delta_fn=None, core=core
        )

    assert stream.closed is True
    assert stream.iterated is False
