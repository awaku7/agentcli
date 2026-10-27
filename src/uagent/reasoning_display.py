from __future__ import annotations

import re
import sys
import unicodedata
from typing import Any, Callable, Optional

from .env_utils import env_get
from .util_tools import get_display_reasoning

_ANSI_CSI_RE = re.compile(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"(?:\x1b\]|\x9d).*?(?:\x07|\x1b\\|\x9c)", re.DOTALL)


def _safe_terminal_text(text: str) -> str:
    """Remove terminal control sequences from untrusted reasoning text."""
    text = _ANSI_CSI_RE.sub("", text)
    text = _ANSI_OSC_RE.sub("", text)
    return "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) != "Cc"
    )


def _enable_vt_if_windows() -> bool:
    """Enable VT (ANSI) processing in the Windows console.

    cmd.exe / conhost does not interpret ANSI escape sequences by default, so
    set ENABLE_VIRTUAL_TERMINAL_PROCESSING to enable colored output.
    """
    if not sys.platform.startswith("win"):
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        pass
    return False


_WINDOWS_VT_ENABLED = _enable_vt_if_windows()


def _reasoning_ansi_enabled(core: Any = None) -> bool:
    """Return whether reasoning can safely use ANSI color on this CLI host."""
    if env_get("NO_COLOR") is not None or env_get("UAGENT_NO_COLOR"):
        return False
    if bool(getattr(core, "IS_GUI", False)):
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    return not sys.platform.startswith("win") or _WINDOWS_VT_ENABLED


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
    # Prefer the core-specific writer so the next assistant delta can insert
    # a clean line boundary after streamed reasoning.
    core_out_fn = (
        getattr(core, "print_reasoning_delta", None) if core is not None else None
    )
    if callable(core_out_fn):
        out_fn = core_out_fn
        writes_to_terminal = True
    elif print_fn is not None:
        out_fn = print_fn
        writes_to_terminal = False
    else:
        out_fn = print
        writes_to_terminal = True
    # Prevent fine-grained DeepSeek reasoning deltas from becoming one-character lines.
    # core.print_status_line checks _stream_line_open for [STATE] and
    # closes the line before displaying, preventing mid-line interruption.
    safe_text = _safe_terminal_text(text)
    if writes_to_terminal and _reasoning_ansi_enabled(core):
        # Gray only the reasoning text and always reset in this same write, so
        # later assistant output cannot inherit reasoning's terminal color.
        safe_text = "\x1b[90m" + safe_text + "\x1b[0m"
    out_fn(label + safe_text)
