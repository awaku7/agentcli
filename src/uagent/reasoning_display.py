from __future__ import annotations
import sys
from typing import Any, Callable, Optional

from .util_tools import get_display_reasoning


def _enable_vt_if_windows() -> None:
    """Enable VT (ANSI) processing in the Windows console.

    cmd.exe / conhost does not interpret ANSI escape sequences by default, so
    set ENABLE_VIRTUAL_TERMINAL_PROCESSING to enable colored output.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


_enable_vt_if_windows()


def show_reasoning(
    text: str,
    *,
    provider: str = "LLM",
    is_first: bool = False,
    print_fn: Optional[Callable[[str], None]] = None,
    core: Any = None,
) -> None:
    if not text:
        return
    # Do not display when the display-only flag is off
    if not get_display_reasoning():
        return
    is_web = bool(getattr(core, "_is_web", False)) if core is not None else False
    if is_web:
        try:
            lm = getattr(core, "log_message", None)
            if callable(lm):
                lm({"type": "assistant_reasoning_delta", "delta": text})
        except Exception:
            pass
        return
    display_provider = (
        provider.capitalize()
        if provider and provider.islower()
        else (provider or "LLM")
    )
    label = ("[" + display_provider + " Reasoning] ") if is_first else ""
    # Do not add ANSI escapes. Depending on the host (cmd/conhost/GUI, etc.), ESC may
    # become "?", resulting in "?[90m...?[0m"; display plain text instead.
    # Prefer the core-specific writer so the next assistant delta can insert
    # a clean line boundary after streamed reasoning.
    out_fn = getattr(core, "print_reasoning_delta", None) if core is not None else None
    if not callable(out_fn):
        out_fn = print_fn if print_fn is not None else print
    # Prevent fine-grained DeepSeek reasoning deltas from becoming one-character lines.
    # core.print_status_line checks _stream_line_open for [STATE] and
    # closes the line before displaying, preventing mid-line interruption.
    out_fn(label + text)
