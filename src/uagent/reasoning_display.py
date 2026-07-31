from __future__ import annotations
import os
import sys
from typing import Any, Callable, Optional

from .util_tools import get_display_reasoning


def _use_ansi() -> bool:
    """ANSI エスケープコードを使うかどうかを判定する。

    - NO_COLOR 環境変数が設定されていれば使わない
    - Windows (cmd.exe 等) では ESC が化けるため使わない
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    if sys.platform.startswith("win"):
        return False
    return True


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
    if _use_ansi():
        out_fn(label + "\x1b[90m" + text + "\x1b[0m")
    else:
        out_fn(label + text)
