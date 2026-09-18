"""Host-owned callback wiring for normalized stream renderers.

This module contains the small amount of CLI/GUI/Web selection needed by
legacy stream parsers. Provider adapters can consume the resulting
``StreamCallbacks`` contract without inspecting host objects themselves.
"""

from __future__ import annotations

from typing import Any

from .stream_renderer import StreamCallbacks


def build_stream_callbacks(
    *, print_delta_fn: Any = None, core: Any = None
) -> StreamCallbacks:
    """Build the common text-delta callback for CLI, GUI, and Web hosts."""

    def on_delta(text: str) -> None:
        if bool(getattr(core, "_is_web", False)) and core is not None:
            log_message = getattr(core, "log_message", None)
            if callable(log_message):
                log_message({"type": "assistant_stream_delta", "delta": text})
            return
        if callable(print_delta_fn):
            print_delta_fn(text)
        else:
            print(text, end="", flush=True)

    return StreamCallbacks(on_delta=on_delta)


__all__ = ["build_stream_callbacks"]
