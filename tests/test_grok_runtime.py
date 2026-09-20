from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.grok_runtime import GrokGrpcProviderRuntime
from uagent.runtime.round_contracts import (
    RoundIdentifiers,
    SerializedRequest,
    validate_stream_events,
)


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False


class _CancelAfter:
    def __init__(self, allowed_checks: int) -> None:
        self.allowed_checks = allowed_checks
        self.checks = 0

    def is_cancelled(self) -> bool:
        self.checks += 1
        return self.checks > self.allowed_checks


class _Chat:
    def __init__(self, stream=()) -> None:
        self.calls = []
        self.stream_values = stream

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stream=lambda: iter(self.stream_values), sample=lambda: SimpleNamespace()
        )


class _Client:
    def __init__(self, stream=()) -> None:
        self.chat = _Chat(stream)


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1)


def _request() -> SerializedRequest:
    return SerializedRequest(
        identifiers=_identifiers(),
        plan_id="plan",
        projection_id="projection",
        provider="grok",
        model="grok-test",
        payload={"model": "grok-test", "messages": [], "tools": []},
    )


def test_grok_runtime_normalizes_sdk_stream(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )

    client = _Client([(None, SimpleNamespace(content="hello"))])
    runtime = GrokGrpcProviderRuntime(
        client=client,
        provider="grok",
        model="grok-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(), _Cancellation()))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert client.chat.calls[0]["messages"] == ["native-message"]


def test_grok_runtime_yields_chunks_incrementally(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )
    consumed: list[str] = []

    def stream():
        for text in ("first", "second"):
            consumed.append(text)
            yield None, SimpleNamespace(content=text)

    runtime = GrokGrpcProviderRuntime(
        client=_Client(stream()),
        provider="grok",
        model="grok-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = runtime.run(_request(), _Cancellation())
    assert next(events).type == "ResponseStarted"
    assert consumed == []
    first_delta = next(events)
    assert first_delta.type == "TextDelta"
    assert first_delta.data["text"] == "first"
    assert consumed == ["first"]
    assert [event.type for event in events] == ["TextDelta", "ResponseCompleted"]
    assert consumed == ["first", "second"]


def test_grok_runtime_preserves_reasoning_text_and_tool_order(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(name="read_file", arguments='{"path":"a"}'),
    )
    stream = [
        (None, SimpleNamespace(reasoning_content="think")),
        (None, SimpleNamespace(content="answer")),
        (None, SimpleNamespace(tool_calls=[tool_call])),
    ]
    runtime = GrokGrpcProviderRuntime(
        client=_Client(stream),
        provider="grok",
        model="grok-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(), _Cancellation()))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ReasoningDelta",
        "TextDelta",
        "ToolCallDelta",
        "ToolCallCompleted",
        "ResponseCompleted",
    ]
    assert events[1].data["text"] == "think"
    assert events[2].data["text"] == "answer"
    assert events[4].data["name"] == "read_file"


def test_grok_runtime_completes_repeated_stream_tool_call_once(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )
    repeated_call = SimpleNamespace(
        id="call-time",
        function=SimpleNamespace(name="get_current_time", arguments="{}"),
    )
    repeated_call_with_new_id = SimpleNamespace(
        id="call-time-repeated",
        function=SimpleNamespace(name="get_current_time", arguments="{}"),
    )
    runtime = GrokGrpcProviderRuntime(
        client=_Client(
            [
                (None, SimpleNamespace(tool_calls=[repeated_call])),
                (None, SimpleNamespace(content="checking")),
                (None, SimpleNamespace(tool_calls=[repeated_call])),
                (
                    None,
                    SimpleNamespace(tool_calls=[repeated_call_with_new_id]),
                ),
            ]
        ),
        provider="grok",
        model="grok-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(), _Cancellation()))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "ToolCallDelta",
        "ToolCallCompleted",
        "ResponseCompleted",
    ]
    completed = [event for event in events if event.type == "ToolCallCompleted"]
    assert len(completed) == 1
    assert completed[0].data["tool_call_id"] == "call-time"
    assert completed[0].data["name"] == "get_current_time"


def test_grok_runtime_keeps_distinct_stream_tool_calls(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )
    calls = [
        SimpleNamespace(
            id="call-location",
            function=SimpleNamespace(name="get_current_location", arguments="{}"),
        ),
        SimpleNamespace(
            id="call-weather",
            function=SimpleNamespace(
                name="get_weather_wttr", arguments='{"location":"Tokyo"}'
            ),
        ),
    ]
    runtime = GrokGrpcProviderRuntime(
        client=_Client([(None, SimpleNamespace(tool_calls=calls))]),
        provider="grok",
        model="grok-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(), _Cancellation()))

    validate_stream_events(events)
    completed = [event for event in events if event.type == "ToolCallCompleted"]
    assert [event.data["tool_call_id"] for event in completed] == [
        "call-location",
        "call-weather",
    ]


def test_grok_runtime_cancels_between_stream_chunks(monkeypatch) -> None:
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_messages",
        lambda messages: (None, ["native-message"]),
    )
    monkeypatch.setattr(
        "uagent.providers.grok_runtime.build_xai_tools",
        lambda enabled, call_messages=None: None,
    )
    consumed: list[str] = []

    def stream():
        for text in ("first", "second", "third"):
            consumed.append(text)
            yield None, SimpleNamespace(content=text)

    runtime = GrokGrpcProviderRuntime(
        client=_Client(stream()),
        provider="grok",
        model="grok-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(runtime.run(_request(), _CancelAfter(3)))

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "ResponseCancelled",
    ]
    assert events[1].data["text"] == "first"
    assert events[2].data["reason"] == "cancelled"
    assert consumed == ["first"]


__all__ = []
