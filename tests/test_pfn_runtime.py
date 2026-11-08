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
    assert client.chat.completions.calls[0]["stream_options"]["include_usage"] is True
    assert events[-1].data == {}


def test_pfn_runtime_normalizes_complete_tool_response() -> None:
    response = SimpleNamespace(
        usage={"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
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
        ],
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
    assert "stream_options" not in client.chat.completions.calls[0]
    assert events[-1].data["usage"] == {
        "input_tokens": 12,
        "output_tokens": 3,
        "total_tokens": 15,
    }


def test_pfn_stream_reports_only_final_measured_usage() -> None:
    chunks = [
        {
            "choices": [{"delta": {"content": "hello"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
        },
        {
            "choices": [{"delta": {"content": " world"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
        {
            "choices": [],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
    ]
    client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions(chunks)))
    runtime = PfnProviderRuntime(
        client=client,
        provider="pfn",
        model="plamo-3.1-prime",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(
        runtime.run(
            _request({"model": "plamo-3.1-prime", "messages": [], "tools": []}),
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
    assert events[-1].data["usage"] == {
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 12,
    }
    assert client.chat.completions.calls[0]["stream_options"]["include_usage"] is True


def test_pfn_stream_without_terminal_usage_does_not_report_partial_counts() -> None:
    chunks = [
        {
            "choices": [{"delta": {"content": "hello"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
        }
    ]
    client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions(chunks)))
    runtime = PfnProviderRuntime(
        client=client,
        provider="pfn",
        model="plamo-3.1-prime",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(
        runtime.run(
            _request({"model": "plamo-3.1-prime", "messages": [], "tools": []}),
            _Cancellation(),
        )
    )

    validate_stream_events(events)
    assert events[-1].type == "ResponseCompleted"
    assert events[-1].data == {}


def test_pfn_stream_respects_explicit_include_usage_false() -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=_Completions([{"choices": [{"delta": {"content": "hello"}}]}])
        )
    )
    runtime = PfnProviderRuntime(
        client=client,
        provider="pfn",
        model="plamo-3.1-prime",
        identifiers=_identifiers(),
        streaming=True,
    )

    events = list(
        runtime.run(
            _request(
                {
                    "model": "plamo-3.1-prime",
                    "messages": [],
                    "tools": [],
                    "stream_options": {"include_usage": False},
                }
            ),
            _Cancellation(),
        )
    )

    validate_stream_events(events)
    assert client.chat.completions.calls[0]["stream_options"] == {
        "include_usage": False
    }
    assert events[-1].data == {}


__all__ = []
