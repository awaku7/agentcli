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
    label = ("[" + display_provider + " Reasoning] ") if is_first else ""
    # ANSI エスケープを付けない。ホスト（cmd/conhost/GUI 等）によって ESC が
    # "?" に化けて "?[90m...?[0m" になるため、プレーンテキストで表示する。
    # デルタごとに改行で閉じない: print_stream_delta (end="") が連結するため、
    # DeepSeek の細かい reasoning デルタが1文字ずつの行になるのを防ぐ。
    # [STATE] は core.print_status_line が _stream_line_open を見て
    # 行を閉じてから表示するので、行の途中に割り込まない。
    out_fn(label + text)
