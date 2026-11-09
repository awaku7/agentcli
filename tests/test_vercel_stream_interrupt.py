"""Abandoned Vercel streams cannot render or publish usage into a new turn."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from uagent import core as core_module
from uagent.llm_helpers import LLMWaitInterrupted, _call_maybe_thread
from uagent.providers.llm_vercel import _parse_vercel_stream
from uagent.runtime.stream_renderer import StreamCallbacks


def _delta(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=text,
                    reasoning_content=None,
                    tool_calls=[],
                )
            )
        ],
        usage=None,
    )


def _usage() -> SimpleNamespace:
    return SimpleNamespace(
        choices=[],
        usage={"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
    )


def test_vercel_successful_stream_only_returns_usage_to_owning_caller(
    monkeypatch,
) -> None:
    monkeypatch.setattr(core_module, "interrupt_requested", False)
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_is_web=False, _last_responses_usage=previous)
    collected: list[dict[str, int]] = []
    deltas: list[str] = []
    response = _parse_vercel_stream(
        [_delta("answer"), _usage()],
        core=core,
        usage_sink=collected,
        callbacks=StreamCallbacks(
            on_delta=deltas.append,
            on_terminal=lambda *_: None,
        ),
    )
    assert response[0] == "answer"
    assert collected == [{"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}]
    # Only vercel_chat_with_tools may publish this to the shared core after
    # the threaded call returns successfully to the owning request.
    assert core._last_responses_usage is previous
    assert deltas[0] == "answer"


def test_vercel_web_stop_suppresses_later_deltas_and_stream_end(monkeypatch) -> None:
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
        _parse_vercel_stream(stream(), core=core)

    assert events == [{"type": "assistant_stream_delta", "delta": "before"}]


def test_abandoned_vercel_worker_stays_silent_after_stop_reset(
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
            _parse_vercel_stream(stream(), core=core, usage_sink=measured)
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
