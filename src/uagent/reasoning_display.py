from __future__ import annotations
import sys
from typing import Any, Callable, Optional

from .util_tools import get_display_reasoning


def _enable_vt_if_windows() -> None:
    """Windows コンソールで VT (ANSI) 処理を有効化する。

    cmd.exe / conhost は既定で ANSI エスケープシーケンスを解釈しないため、
    ENABLE_VIRTUAL_TERMINAL_PROCESSING を設定して色付き表示を可能にする。
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
    # 表示専用フラグが off なら表示しない
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
    out_fn = print_fn if print_fn is not None else print
    display_provider = (
        provider.capitalize()
        if provider and provider.islower()
        else (provider or "LLM")
    )
    label = ("[" + display_provider + " Reasoning]" + "\n") if is_first else ""
    out_fn(label + "\x1b[90m" + text + "\x1b[0m")
