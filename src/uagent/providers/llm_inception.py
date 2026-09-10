"""Inception/Mercury Chat Completions streaming helpers."""

from __future__ import annotations

import sys
from typing import Any


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
    text_parts: list[str] = []
    latest_text = ""
    tool_calls_acc: dict[int, dict[str, Any]] = {}
    displayed_lines = 0

    try:
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue

            content_delta = getattr(delta, "content", None)
            if isinstance(content_delta, str) and content_delta:
                if diffusing:
                    latest_text = content_delta
                    displayed_lines = _emit_snapshot(
                        latest_text,
                        print_delta_fn=print_delta_fn,
                        core=core,
                        previous_lines=displayed_lines,
                    )
                else:
                    text_parts.append(content_delta)
                    if print_delta_fn and not bool(getattr(core, "_is_web", False)):
                        print_delta_fn(content_delta)
                    elif bool(getattr(core, "_is_web", False)) and core is not None:
                        log_message = getattr(core, "log_message", None)
                        if callable(log_message):
                            log_message(
                                {
                                    "type": "assistant_stream_delta",
                                    "delta": content_delta,
                                }
                            )

            tool_deltas = getattr(delta, "tool_calls", None) or []
            for tool_delta in tool_deltas:
                index = getattr(tool_delta, "index", 0) or 0
                acc = tool_calls_acc.setdefault(
                    index,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                tool_id = getattr(tool_delta, "id", None)
                if isinstance(tool_id, str) and tool_id:
                    acc["id"] = tool_id
                fn_delta = getattr(tool_delta, "function", None)
                if fn_delta is not None:
                    name = getattr(fn_delta, "name", None)
                    arguments = getattr(fn_delta, "arguments", None)
                    if isinstance(name, str):
                        acc["function"]["name"] += name
                    if isinstance(arguments, str):
                        acc["function"]["arguments"] += arguments
    except Exception:
        # Match the tolerant behavior of the other provider stream parsers.
        pass

    result_text = latest_text if diffusing else "".join(text_parts)
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

    tool_calls = [
        item for _, item in sorted(tool_calls_acc.items()) if item["function"]["name"]
    ]
    return result_text, "", tool_calls
