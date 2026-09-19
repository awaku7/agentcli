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


class _Chat:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stream=lambda: iter(()), sample=lambda: SimpleNamespace()
        )


class _Client:
    def __init__(self) -> None:
        self.chat = _Chat()


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

    def parse_stream(stream, *, callbacks):
        callbacks.on_delta("hello")
        return "hello", []

    monkeypatch.setattr("uagent.providers.grok_runtime.parse_xai_stream", parse_stream)
    client = _Client()
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


__all__ = []
