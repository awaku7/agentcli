"""Inception/Mercury Chat Completions streaming helpers."""

from __future__ import annotations

import json

import time
import uuid
from typing import Any, Iterator

from ..runtime.round_contracts import RoundIdentifiers, StreamEvent
from ..runtime.inception_stream_compat import collect_inception_stream_events
from .responses_runtime import _responses_session_generation


def inception_stream_events(
    stream: Any,
    *,
    identifiers: RoundIdentifiers,
    diffusing: bool = False,
    cancellation: Any = None,
) -> Iterator[StreamEvent]:
    """Convert an Inception stream into provider-neutral ``StreamEvent`` values.

    This adapter deliberately performs no CLI, GUI, or Web rendering. The
    existing :func:`parse_inception_stream` remains a compatibility wrapper.
    """

    sequence = 0

    def emit(event_type: str, data: dict[str, Any] | None = None) -> StreamEvent:
        nonlocal sequence
        event = StreamEvent(
            type=event_type,
            identifiers=identifiers,
            sequence_number=sequence,
            timestamp=time.time(),
            data=data or {},
        )
        sequence += 1
        return event

    try:
        yield emit(
            "ResponseStarted",
            {"stream_mode": "snapshot" if diffusing else "delta"},
        )
    except GeneratorExit:
        close = getattr(stream, "close", None)
        if callable(close):
            close()
        raise

    tool_calls_acc: dict[int, dict[str, str]] = {}

    try:
        for chunk in stream:
            if cancellation is not None and bool(
                getattr(cancellation, "is_cancelled", lambda: False)()
            ):
                yield emit("ResponseCancelled", {"reason": "cancelled"})
                return

            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue

            content_delta = getattr(delta, "content", None)
            if isinstance(content_delta, str) and content_delta:
                event_type = "TextSnapshot" if diffusing else "TextDelta"
                yield emit(event_type, {"text": content_delta})

            tool_deltas = getattr(delta, "tool_calls", None) or []
            for tool_delta in tool_deltas:
                index = int(getattr(tool_delta, "index", 0) or 0)
                acc = tool_calls_acc.setdefault(
                    index, {"id": "", "name": "", "arguments": ""}
                )
                tool_id = getattr(tool_delta, "id", None)
                if isinstance(tool_id, str) and tool_id and not acc["id"]:
                    acc["id"] = tool_id
                # Some providers omit the id on later fragments. Keep a stable
                # adapter-local id so all fragments share one key.
                call_id = acc["id"] or f"inception-tool-{index}"
                acc["id"] = call_id
                fn_delta = getattr(tool_delta, "function", None)
                name = getattr(fn_delta, "name", None) if fn_delta else None
                arguments = getattr(fn_delta, "arguments", None) if fn_delta else None
                name_fragment = name if isinstance(name, str) else ""
                arguments_fragment = arguments if isinstance(arguments, str) else ""
                acc["name"] += name_fragment
                acc["arguments"] += arguments_fragment
                yield emit(
                    "ToolCallDelta",
                    {
                        "index": index,
                        "tool_call_id": call_id,
                        "name_fragment": name_fragment,
                        "arguments_fragment": arguments_fragment,
                    },
                )

        for index, call in sorted(tool_calls_acc.items()):
            arguments: Any = call["arguments"]
            try:
                validated_arguments: Any = json.loads(arguments)
            except (TypeError, ValueError):
                validated_arguments = None
            yield emit(
                "ToolCallCompleted",
                {
                    "index": index,
                    "tool_call_id": call["id"],
                    "name": call["name"],
                    "arguments": arguments,
                    "validated_arguments": validated_arguments,
                },
            )
        yield emit("ResponseCompleted", {})
    except TimeoutError:
        yield emit("ResponseTimedOut", {"reason": "timeout"})
    except Exception as exc:
        yield emit(
            "ResponseFailed",
            {"error_type": type(exc).__name__, "message": str(exc)},
        )
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()


def parse_inception_stream(
    stream: Any,
    *,
    diffusing: bool = False,
    print_delta_fn: Any = None,
    core: Any = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Consume an Inception streaming response.

    Normal streaming returns incremental content deltas. In diffusion mode,
    each content delta is the complete refined snapshot and must replace the
    previous display instead of being concatenated.
    """
    stream_id = "inception-" + uuid.uuid4().hex
    identifiers = RoundIdentifiers(
        turn_id="compat-" + stream_id,
        round_id="compat-" + stream_id,
        attempt_id="compat-" + stream_id,
        request_id="compat-" + stream_id,
        stream_id=stream_id,
        session_generation=_responses_session_generation(core),
    )
    events = inception_stream_events(
        stream,
        identifiers=identifiers,
        diffusing=diffusing,
        cancellation=getattr(core, "cancellation_token", None),
    )
    return collect_inception_stream_events(
        events,
        diffusing=diffusing,
        print_delta_fn=print_delta_fn,
        core=core,
    )
