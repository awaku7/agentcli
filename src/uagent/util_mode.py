"""Reasoning / verbosity mode management (moved from util_tools.py)."""

from __future__ import annotations

import os
from typing import Any

from .env_utils import env_get
from .i18n import _

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _

_REASONING_LEVELS = ["off", "auto", "minimal", "low", "medium", "high", "xhigh", "max"]

_VERBOSITY_LEVELS = ["off", "low", "medium", "high"]


def get_reasoning_mode() -> str:
    v = (env_get("UAGENT_REASONING") or "").strip().lower()
    return v if v in _REASONING_LEVELS and v != "off" else "off"


def get_verbosity_mode() -> str:
    v = (env_get("UAGENT_VERBOSITY") or "").strip().lower()
    return v if v in _VERBOSITY_LEVELS and v != "off" else "off"


def _normalize_off_arg(a: str) -> str | None:
    if a in ("0", "off", "none", "no", "false", "disable", "disabled"):
        return "off"
    return None


def _normalize_reasoning_level_arg(arg: str) -> str | None:
    a = (arg or "").strip().lower()
    if not a:
        return None

    off = _normalize_off_arg(a)
    if off is not None:
        return off

    if a in ("auto", "a"):
        return "auto"
    if a in ("minimal", "min"):
        return "minimal"
    if a in ("1", "low"):
        return "low"
    if a in ("2", "mid", "middle", "medium"):
        return "medium"
    if a in ("3", "high"):
        return "high"
    if a in ("4", "xhigh", "xh", "x-high"):
        return "xhigh"
    if a in ("5", "max", "m"):
        return "max"

    return None


def _normalize_verbosity_level_arg(arg: str) -> str | None:
    a = (arg or "").strip().lower()
    if not a:
        return None

    off = _normalize_off_arg(a)
    if off is not None:
        return off

    if a in ("1", "low"):
        return "low"
    if a in ("2", "mid", "middle", "medium"):
        return "medium"
    if a in ("3", "high"):
        return "high"

    return None


def _cycle_level(cur: str, levels: list[str]) -> str:
    c = (cur or "off").strip().lower()
    if c not in levels:
        c = "off"
    idx = levels.index(c)
    return levels[(idx + 1) % len(levels)]


def set_reasoning_mode(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv not in _REASONING_LEVELS:
        lv = "off"
    if lv == "off":
        os.environ.pop("UAGENT_REASONING", None)
    else:
        os.environ["UAGENT_REASONING"] = lv
    return get_reasoning_mode()


def set_verbosity_mode(level: str) -> str:
    lv = (level or "off").strip().lower()
    if lv not in _VERBOSITY_LEVELS:
        lv = "off"
    if lv == "off":
        os.environ.pop("UAGENT_VERBOSITY", None)
    else:
        os.environ["UAGENT_VERBOSITY"] = lv
    return get_verbosity_mode()


_REASONING_HISTORY: list[str] = ["medium"]

_DISPLAY_REASONING: bool = True


def get_display_reasoning() -> bool:
    """Return whether reasoning content should be displayed to the user."""
    return _DISPLAY_REASONING


def extract_last_assistant_text(messages: list) -> str:
    """messages 末尾から最後の assistant テキスト応答を取り出す。

    tool 呼び出しのみの assistant メッセージはスキップし、最後の
    テキスト応答を返す。content がリスト (マルチモーダル) の場合は
    text パートを連結する。bitchat への自動返信などに使う。
    """
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        if msg.get("tool_calls"):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item.get("content"), str):
                        parts.append(item["content"])
            text = "".join(parts).strip()
        else:
            continue
        if text:
            return text
    return ""


def apply_reasoning_arg(arg: str) -> str:
    global _REASONING_HISTORY, _DISPLAY_REASONING
    lv = _normalize_reasoning_level_arg(arg)
    if lv is None and (arg or "").strip():
        # invalid (non-empty)
        raise ValueError(tr("invalid reasoning"))

    # No arg given: toggle display only (do not touch env var / API reasoning)
    if lv is None:
        _DISPLAY_REASONING = not _DISPLAY_REASONING
        status = "on" if _DISPLAY_REASONING else "off"
        print(_("[display] reasoning display=%(mode)s") % {"mode": status})
        return get_reasoning_mode()

    # Value given: set both env var and display flag
    _DISPLAY_REASONING = lv != "off"
    return set_reasoning_mode(lv)


def apply_verbosity_arg(arg: str) -> str:
    cur = get_verbosity_mode()

    # If no arg is given, keep current mode (do not change).
    if not (arg or "").strip():
        return cur

    lv = _normalize_verbosity_level_arg(arg)
    if lv is None:
        raise ValueError(tr("invalid verbosity"))
    return set_verbosity_mode(lv)


def _handle_cmd_reasoning(arg: str, *, tr: Any) -> bool:
    try:
        new_mode = apply_reasoning_arg(arg)
    except Exception:
        print(
            _(
                ":r [0|1|2|3|auto|minimal|xhigh]  (0=off, 1=low, 2=medium, 3=high; auto/minimal/xhigh)"
            )
        )
        return True

    print(_("[mode] reasoning=%(mode)s") % {"mode": new_mode})
    return True


def _handle_cmd_verbosity(arg: str, *, tr: Any) -> bool:
    try:
        new_mode = apply_verbosity_arg(arg)
    except Exception:
        print(_(":v [0|1|2|3]  (0=off, 1=low, 2=medium, 3=high; no arg=keep)"))
        return True

    print(_("[mode] verbosity=%(mode)s") % {"mode": new_mode})
    return True
