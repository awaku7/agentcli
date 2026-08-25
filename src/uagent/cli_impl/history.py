"""Prompt history helpers (split from cli.py)."""

from __future__ import annotations

import os
from typing import Any

from . import state
from .. import util_tools as tools_util
from ..utils.paths import get_history_file_path


def _append_prompt_history_entry(text: str) -> None:
    normalized = tools_util.strip_surrogates((text or "").replace("\r", "").strip())
    if not normalized:
        return
    if normalized not in state._PROMPT_HISTORY:
        state._PROMPT_HISTORY.append(normalized)

    for session in (state._PROMPT_SESSION, state._PROMPT_REPLY_SESSION):
        if session is None:
            continue
        history = getattr(session, "history", None)
        append_string = getattr(history, "append_string", None)
        if callable(append_string):
            try:
                append_string(normalized)
            except Exception:
                pass


def _bootstrap_prompt_history(messages: list[dict[str, Any]]) -> None:
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            _append_prompt_history_entry(content)


def _persist_prompt_history_entry(text: str) -> None:
    normalized = tools_util.strip_surrogates(
        (text or "")
        .replace(
            "\
",
            "",
        )
        .strip()
    )
    if not normalized:
        return

    try:
        from datetime import datetime

        history_path = get_history_file_path()
        os.makedirs(history_path.parent, exist_ok=True)
        with open(history_path, "ab") as f:
            f.write(f"\
# {datetime.now()}\
".encode("utf-8"))
            for line in normalized.split("\
"):
                f.write(f"+{line}\
".encode("utf-8"))
    except Exception:
        pass
