"""Grok gRPC reported-usage regression tests without network or live credentials."""

from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.grok_runtime import GrokGrpcProviderRuntime
from uagent.providers.llm_grok import parse_xai_stream
from uagent.runtime.round_contracts import RoundIdentifiers, SerializedRequest
from uagent.runtime.stream_renderer import StreamCallbacks


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False


class _CancelAfter:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.checks = 0

    def is_cancelled(self) -> bool:
        self.checks += 1
        return self.checks > self.limit


class _Client:
    def __init__(self, *, stream=(), response=None) -> None:
        self.chunks = stream
        self.response = response
        self.chat = SimpleNamespace(create=self._create)

    def _create(self, **_kwargs):
        return SimpleNamespace(
            stream=lambda: iter(self.chunks),
            sample=lambda: self.response,
        )


def _usage(prompt: int, completion: int, reasoning: int, cache: int = 0):
    return SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        reasoning_tokens=reasoning,
        cached_prompt_text_tokens=cache,
    )


def _request() -> SerializedRequest:
    return SerializedRequest(
        identifiers=RoundIdentifiers(
            "turn", "round", "attempt", "request", "stream", 1
        ),
        plan_id="plan",
        projection_id="projection",
        provider="grok",
        model="grok-test",
        payload={"model": "grok-test", "messages": [], "tools": []},
    )


def _runtime(monkeypatch, *, stream=(), response=None, streaming=True):
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda _messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda *_args, **_kwargs: None,
    )
    return GrokGrpcProviderRuntime(
        client=_Client(stream=stream, response=response),
        provider="grok",
        model="grok-test",
        identifiers=_request().identifiers,
        streaming=streaming,
    )


def _expected_usage():
    return {
        "input_tokens": 110,
        "output_tokens": 35,
        "total_tokens": 145,
        "cache_read_input_tokens": 40,
        "reasoning_output_tokens": 23,
    }


def test_grok_registry_nonstream_exposes_measured_usage(monkeypatch) -> None:
    response = SimpleNamespace(
        content="answer",
        tool_calls=[],
        usage=_usage(110, 12, 23, 40),
    )
    runtime = _runtime(monkeypatch, response=response, streaming=False)
    events = list(runtime.run(_request(), _Cancellation()))
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert events[-1].data == {"usage": _expected_usage()}


def test_grok_registry_stream_uses_last_cumulative_usage(monkeypatch) -> None:
    stream = [
        (
            SimpleNamespace(usage=_usage(10, 1, 1)),
            SimpleNamespace(content="a"),
        ),
        (
            SimpleNamespace(usage=_usage(110, 12, 23, 40)),
            SimpleNamespace(content="b"),
        ),
    ]
    runtime = _runtime(monkeypatch, stream=stream)
    events = list(runtime.run(_request(), _Cancellation()))
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert events[-1].data == {"usage": _expected_usage()}


def test_grok_registry_cancel_does_not_export_partial_usage(monkeypatch) -> None:
    stream = [
        (
            SimpleNamespace(usage=_usage(10, 1, 1)),
            SimpleNamespace(content="a"),
        ),
        (
            SimpleNamespace(usage=_usage(110, 12, 23, 40)),
            SimpleNamespace(content="b"),
        ),
    ]
    runtime = _runtime(monkeypatch, stream=stream)
    events = list(runtime.run(_request(), _CancelAfter(3)))
    assert events[-1].type == "ResponseCancelled"
    assert "usage" not in events[-1].data


def test_grok_registry_stream_failure_has_no_partial_usage(monkeypatch) -> None:
    def stream():
        yield SimpleNamespace(usage=_usage(10, 1, 1)), SimpleNamespace(content="a")
        raise RuntimeError("stream interrupted")

    runtime = _runtime(monkeypatch, stream=stream())
    events = list(runtime.run(_request(), _Cancellation()))
    assert events[-1].type == "ResponseFailed"
    assert "usage" not in events[-1].data


def test_grok_legacy_stream_stores_only_completed_usage_snapshot() -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)
    events = [
        (SimpleNamespace(usage=_usage(10, 1, 1)), SimpleNamespace(content="a")),
        (
            SimpleNamespace(usage=_usage(110, 12, 23, 40)),
            SimpleNamespace(content="b"),
        ),
    ]
    parse_xai_stream(
        events,
        core=core,
        callbacks=StreamCallbacks(on_delta=lambda _text: None),
    )
    assert core._last_responses_usage == _expected_usage()


def test_grok_legacy_incomplete_stream_keeps_prior_snapshot() -> None:
    previous = {"input_tokens": 999}
    core = SimpleNamespace(_last_responses_usage=previous)

    def stream():
        yield SimpleNamespace(usage=_usage(10, 1, 1)), SimpleNamespace(content="a")
        raise RuntimeError("stream interrupted")

    parse_xai_stream(
        stream(),
        core=core,
        callbacks=StreamCallbacks(on_delta=lambda _text: None),
    )
    assert core._last_responses_usage is previous
