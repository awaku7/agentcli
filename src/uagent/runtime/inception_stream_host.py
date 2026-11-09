"""Host-owned rendering for normalized Inception stream events.

The Inception provider adapter emits only provider-neutral ``StreamEvent``
values.  This module owns the historical CLI/GUI/Web display behavior used by
round orchestration and compatibility callers.  Provider code must not import
this module to parse provider responses; it only consumes normalized events.
"""

from __future__ import annotations

import sys
from typing import Any, Iterable

from .round_contracts import StreamEvent
from .stream_renderer import CallbackStreamRenderer, StreamCallbacks


def _inception_stream_interrupted(core: Any) -> bool:
    """Reject obsolete worker output even after a newer turn resets Stop."""
    from .. import core as core_module
    from ..llm_helpers import llm_call_abandoned

    if llm_call_abandoned():
        return True
    with core_module.interrupt_lock:
        if core_module.interrupt_requested:
            return True
    if bool(getattr(core, "interrupt_requested", False)):
        return True
    cancellation = getattr(core, "cancellation_token", None)
    return cancellation is not None and cancellation.is_cancelled()


def _raise_if_interrupted(core: Any) -> None:
    if _inception_stream_interrupted(core):
        from ..llm_helpers import LLMWaitInterrupted

        raise LLMWaitInterrupted("Inception stream interrupted")


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


def build_inception_stream_callbacks(
    *, print_delta_fn: Any = None, core: Any = None
) -> StreamCallbacks:
    """Build the common callback bundle for CLI, GUI, and Web hosts."""

    displayed_lines = 0

    def on_delta(text: str) -> None:
        if print_delta_fn and not bool(getattr(core, "_is_web", False)):
            print_delta_fn(text)
        elif bool(getattr(core, "_is_web", False)) and core is not None:
            log_message = getattr(core, "log_message", None)
            if callable(log_message):
                log_message({"type": "assistant_stream_delta", "delta": text})
        elif not bool(getattr(core, "_is_web", False)):
            print(text, end="", flush=True)

    def on_snapshot(text: str) -> None:
        nonlocal displayed_lines
        displayed_lines = _emit_snapshot(
            text,
            print_delta_fn=print_delta_fn,
            core=core,
            previous_lines=displayed_lines,
        )

    return StreamCallbacks(on_delta=on_delta, on_snapshot=on_snapshot)


def render_inception_stream_events(
    events: Iterable[StreamEvent],
    *,
    diffusing: bool = False,
    print_delta_fn: Any = None,
    core: Any = None,
    callbacks: StreamCallbacks | None = None,
    usage_sink: list[dict[str, int]] | None = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Render and collect normalized Inception events at the host boundary.

    The renderer receives explicit normalized events and is therefore
    independent of the provider SDK.  ``core`` is accepted only here, at the
    host-owned display boundary, to preserve the legacy CLI/GUI/Web behavior.
    """
    renderer = CallbackStreamRenderer(
        callbacks=callbacks
        or build_inception_stream_callbacks(
            print_delta_fn=print_delta_fn,
            core=core,
        )
    )
    _raise_if_interrupted(core)
    for event in events:
        _raise_if_interrupted(core)
        renderer.on_event(event)
    _raise_if_interrupted(core)

    rendered = renderer.result()
    result_text = rendered.assistant_text
    terminal = rendered.terminal_type
    tool_calls: list[dict[str, Any]] = []
    for data in rendered.tool_calls:
        name = data.get("name")
        if not isinstance(name, str) or not name:
            continue
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
        if terminal == "ResponseCompleted":
            measured_usage = rendered.terminal_data.get("usage")
            if isinstance(measured_usage, dict) and measured_usage:
                # Threaded legacy calls must publish only after their waiter
                # returns; direct host consumers retain their old behavior.
                if usage_sink is not None:
                    usage_sink.append(dict(measured_usage))
                else:
                    core._last_responses_usage = dict(measured_usage)
    return result_text, "", tool_calls


__all__ = [
    "build_inception_stream_callbacks",
    "render_inception_stream_events",
]
