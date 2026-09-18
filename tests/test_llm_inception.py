from __future__ import annotations

import types

from uagent.providers.llm_inception import (
    inception_stream_events,
    parse_inception_stream,
)
from uagent.runtime.round_contracts import RoundIdentifiers, validate_stream_events


class _Chunk:
    def __init__(self, content: str) -> None:
        self.choices = [
            types.SimpleNamespace(
                delta=types.SimpleNamespace(content=content, tool_calls=[])
            )
        ]


def test_diffusing_stream_replaces_snapshots() -> None:
    output: list[str] = []
    result = parse_inception_stream(
        [_Chunk("H"), _Chunk("He"), _Chunk("Hello")],
        diffusing=True,
        print_delta_fn=output.append,
        core=types.SimpleNamespace(_is_web=False),
    )

    assert result[0] == "Hello"
    assert any("Hello" in item for item in output)


def test_normal_stream_concatenates_deltas() -> None:
    result = parse_inception_stream(
        [_Chunk("Hel"), _Chunk("lo")],
        diffusing=False,
        print_delta_fn=lambda _: None,
        core=types.SimpleNamespace(_is_web=False),
    )

    assert result[0] == "Hello"


def test_compatibility_collector_records_normalized_terminal_event() -> None:
    core = types.SimpleNamespace(_is_web=False)

    parse_inception_stream([_Chunk("ok")], core=core)

    assert core._last_inception_stream_terminal == "ResponseCompleted"


def test_compatibility_collector_uses_responses_runtime_generation(monkeypatch) -> None:
    captured: dict[str, RoundIdentifiers] = {}

    def fake_stream_events(stream, *, identifiers, diffusing=False, cancellation=None):
        captured["identifiers"] = identifiers
        return iter(())

    monkeypatch.setattr(
        "uagent.providers.llm_inception.inception_stream_events",
        fake_stream_events,
    )
    core = types.SimpleNamespace(
        _is_web=False,
        session_generation=1,
        responses_runtime=types.SimpleNamespace(session_generation=7),
    )

    parse_inception_stream([_Chunk("ok")], core=core)

    assert captured["identifiers"].session_generation == 7


class _ClosableStream:
    def __init__(self) -> None:
        self.closed = False
        self._chunks = iter([_Chunk("first"), _Chunk("second")])

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._chunks)

    def close(self) -> None:
        self.closed = True


class _Cancelled:
    def __init__(self, cancelled: bool = True) -> None:
        self.cancelled = cancelled

    def is_cancelled(self) -> bool:
        return self.cancelled


def _identifiers() -> RoundIdentifiers:
    return RoundIdentifiers(
        turn_id="turn-1",
        round_id="round-1",
        attempt_id="attempt-1",
        request_id="request-1",
        stream_id="stream-1",
        session_generation=1,
    )


def test_inception_delta_adapter_emits_valid_terminal_stream() -> None:
    events = list(
        inception_stream_events(
            [_Chunk("Hel"), _Chunk("lo")],
            identifiers=_identifiers(),
            diffusing=False,
        )
    )

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextDelta",
        "TextDelta",
        "ResponseCompleted",
    ]


def test_inception_snapshot_adapter_never_mixes_delta_events() -> None:
    events = list(
        inception_stream_events(
            [_Chunk("H"), _Chunk("He"), _Chunk("Hello")],
            identifiers=_identifiers(),
            diffusing=True,
        )
    )

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "TextSnapshot",
        "TextSnapshot",
        "TextSnapshot",
        "ResponseCompleted",
    ]
    assert events[-2].data["text"] == "Hello"


def test_inception_adapter_emits_tool_call_completion_before_terminal() -> None:
    function = types.SimpleNamespace(name="read_file", arguments='{"path":"a"}')
    tool_call = types.SimpleNamespace(id="call-1", index=0, function=function)
    chunk = types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                delta=types.SimpleNamespace(content=None, tool_calls=[tool_call])
            )
        ]
    )

    events = list(
        inception_stream_events([chunk], identifiers=_identifiers(), diffusing=False)
    )

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ToolCallDelta",
        "ToolCallCompleted",
        "ResponseCompleted",
    ]
    assert events[2].data["validated_arguments"] == {"path": "a"}


def test_inception_adapter_emits_cancel_terminal_event() -> None:
    events = list(
        inception_stream_events(
            [_Chunk("ignored")],
            identifiers=_identifiers(),
            cancellation=_Cancelled(),
        )
    )

    validate_stream_events(events)
    assert [event.type for event in events] == [
        "ResponseStarted",
        "ResponseCancelled",
    ]


def test_inception_adapter_closes_provider_stream_on_consumer_close() -> None:
    stream = _ClosableStream()
    events = inception_stream_events(stream, identifiers=_identifiers())

    next(events)
    events.close()

    assert stream.closed is True


def test_inception_host_callback_bundle_falls_back_to_stdout(capsys) -> None:
    from uagent.runtime.inception_stream_host import build_inception_stream_callbacks

    callbacks = build_inception_stream_callbacks(
        core=types.SimpleNamespace(_is_web=False)
    )
    assert callbacks.on_delta is not None
    callbacks.on_delta("ok")

    assert capsys.readouterr().out == "ok"


def test_callback_renderer_accepts_common_host_callback_bundle() -> None:
    from uagent.runtime.stream_renderer import CallbackStreamRenderer, StreamCallbacks

    deltas: list[str] = []
    renderer = CallbackStreamRenderer(
        callbacks=StreamCallbacks(on_delta=deltas.append)
    )
    events = inception_stream_events(
        [_Chunk("ok")], identifiers=_identifiers(), diffusing=False
    )
    for event in events:
        renderer.on_event(event)

    assert deltas == ["ok"]
    assert renderer.result().assistant_text == "ok"
