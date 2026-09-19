from __future__ import annotations

from types import SimpleNamespace

from uagent.providers.pfn_runtime import PfnProviderRuntime
from uagent.runtime.round_contracts import (
    RoundIdentifiers,
    SerializedRequest,
    validate_stream_events,
)


class _Cancellation:
    def is_cancelled(self) -> bool:
        return False


class _Completions:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.response) if kwargs.get("stream") else self.response


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers("turn", "round", "attempt", "request", "stream", 1)


def _request(payload: dict) -> SerializedRequest:
    return SerializedRequest(
        identifiers=_identifiers(),
        plan_id="plan",
        projection_id="projection",
        provider="pfn",
        model="plamo-test",
        payload=payload,
    )


def test_pfn_runtime_normalizes_text_stream() -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=_Completions(
                [
                    {"choices": [{"delta": {"content": "hello"}}]},
                    {"choices": [{"delta": {"content": " world"}}]},
                ]
            )
        )
    )
    runtime = PfnProviderRuntime(
        client=client,
        provider="pfn",
        model="plamo-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(
        runtime.run(
            _request({"model": "plamo-test", "messages": [], "tools": []}),
            _Cancellation(),
        )
    )

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "TextDelta",
        "ResponseCompleted",
    ]
    assert client.chat.completions.calls[0]["stream"] is True


def test_pfn_runtime_normalizes_complete_tool_response() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id="call-1",
                            function=SimpleNamespace(
                                name="read_file", arguments='{"path":"a"}'
                            ),
                        )
                    ],
                )
            )
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions(response)))
    runtime = PfnProviderRuntime(
        client=client,
        provider="pfn",
        model="plamo-test",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(
        runtime.run(
            _request(
                {
                    "model": "plamo-test",
                    "messages": [],
                    "tools": [{"type": "function"}],
                }
            ),
            _Cancellation(),
        )
    )

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ToolCallDelta",
        "ToolCallCompleted",
        "ResponseCompleted",
    ]
    assert events[2].data["name"] == "read_file"
    assert client.chat.completions.calls[0]["stream"] is False


__all__ = []
