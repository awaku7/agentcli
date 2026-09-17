"""Inception/Mercury Chat Completions streaming helpers."""

from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any, Iterator

from ..runtime.round_contracts import RoundIdentifiers, StreamEvent
from ..runtime.stream_renderer import CallbackStreamRenderer
from .responses_runtime import _responses_session_generation


def _emit_snapshot(
    text: str, *, print_delta_fn: Any, core: Any, previous_lines: int = 0
) -> int:
    """Render one diffusion snapshot without appending it to the previous one."""
    if core is not None and bool(getattr(core, "_is_web", False)):
        log_message = getattr(core, "log_message", None)
        if callable(log_message):
            log_message({"type": "assistant_stream_replace", "content": text})
        return max(1, text.count(chr(10)) + 1)
    gui_callback = getattr(core, "_inception_diffusion_callback", None)
    if callable(gui_callback):
        gui_callback(text)
        return max(1, text.count(chr(10)) + 1)
    if print_delta_fn:
        # ANSI erase-line is supported by the CLI terminal setup. Clear the
        # complete previous snapshot, including multi-line output.
        try:
            is_tty = bool(sys.stdout.isatty())
        except Exception:
            is_tty = False
        line_count = max(1, text.count(chr(10)) + 1)
        if is_tty:
            prefix = chr(13)
            if previous_lines > 1:
                prefix += chr(27) + "[" + str(previous_lines - 1) + "A"
            for index in range(previous_lines):
                prefix += chr(27) + "[2K"
                if index < previous_lines - 1:
                    prefix += chr(27) + "[1B" + chr(13)
            if previous_lines > 1:
                prefix += chr(27) + "[" + str(previous_lines - 1) + "A" + chr(13)
            print_delta_fn(prefix + text)
        else:
            # Non-TTY output cannot reliably redraw multi-line snapshots.
            # Buffering until the final snapshot avoids repeated/garbled text.
            return line_count
        return line_count
    return max(1, text.count(chr(10)) + 1)


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


def collect_inception_stream_events(
    events: Iterator[StreamEvent],
    *,
    diffusing: bool = False,
    print_delta_fn: Any = None,
    core: Any = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Render and collect normalized events for the compatibility API.

    Rendering is intentionally downstream of :func:`inception_stream_events`.
    CLI, GUI, and Web can replace this collector independently while the
    provider adapter continues to expose the same event contract.
    """
    tool_calls: list[dict[str, Any]] = []
    displayed_lines = 0
    terminal = ""

    def on_delta(text: str) -> None:
        if print_delta_fn and not bool(getattr(core, "_is_web", False)):
            print_delta_fn(text)
        elif bool(getattr(core, "_is_web", False)) and core is not None:
            log_message = getattr(core, "log_message", None)
            if callable(log_message):
                log_message({"type": "assistant_stream_delta", "delta": text})

    def on_snapshot(text: str) -> None:
        nonlocal displayed_lines
        displayed_lines = _emit_snapshot(
            text,
            print_delta_fn=print_delta_fn,
            core=core,
            previous_lines=displayed_lines,
        )

    def on_tool_call(data: Any) -> None:
        name = data.get("name") if isinstance(data, dict) else None
        if not isinstance(name, str) or not name:
            return
        tool_calls.append(
            {
                "id": str(data.get("tool_call_id") or ""),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": str(data.get("arguments") or ""),
                },
            }
        )

    def on_terminal(event_type: str, _data: Any) -> None:
        nonlocal terminal
        terminal = event_type

    renderer = CallbackStreamRenderer(
        on_delta=on_delta,
        on_snapshot=on_snapshot,
        on_tool_call=on_tool_call,
        on_terminal=on_terminal,
    )
    for event in events:
        renderer.on_event(event)

    rendered = renderer.result()
    result_text = rendered.assistant_text
    gui_callback = getattr(core, "_inception_diffusion_callback", None)
    if callable(gui_callback) and diffusing:
        gui_callback(None)
    if (
        not bool(getattr(core, "_is_web", False))
        and result_text
        and print_delta_fn
        and not (diffusing and callable(gui_callback))
    ):
        try:
            is_tty = bool(sys.stdout.isatty())
        except Exception:
            is_tty = False
        if diffusing and not is_tty:
            print_delta_fn(result_text + chr(10))
        else:
            print_delta_fn(chr(10))
    elif bool(getattr(core, "_is_web", False)) and core is not None:
        log_message = getattr(core, "log_message", None)
        if callable(log_message):
            log_message({"type": "assistant_stream_end"})

    if core is not None:
        try:
            core._last_inception_stream_terminal = terminal
        except Exception:
            pass
    return result_text, "", tool_calls
