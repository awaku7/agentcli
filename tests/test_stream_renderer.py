from __future__ import annotations

from uagent.runtime.round_contracts import RoundIdentifiers, StreamEvent
from uagent.runtime.stream_renderer import CallbackStreamRenderer, StreamCallbacks


def _event(event_type: str, **data: str) -> StreamEvent:
    identifiers = RoundIdentifiers(
        turn_id="turn",
        round_id="round",
        attempt_id="attempt",
        request_id="request",
        stream_id="stream",
        session_generation=1,
    )
    return StreamEvent(
        type=event_type,
        identifiers=identifiers,
        sequence_number=0,
        timestamp=0.0,
        data=data,
    )


def test_explicit_legacy_callback_overrides_callback_bundle() -> None:
    bundled: list[str] = []
    explicit: list[str] = []
    renderer = CallbackStreamRenderer(
        callbacks=StreamCallbacks(on_delta=bundled.append),
        on_delta=explicit.append,
    )

    renderer.on_event(_event("TextDelta", text="answer"))

    assert explicit == ["answer"]
    assert bundled == []
    assert renderer.result().assistant_text == "answer"
