from __future__ import annotations

import json
from typing import Any, Callable

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _skills_marker_prefix() -> str:
    return _("skill.prefix", default="[SKILL] ")


def _clear_skill_messages(messages_ref: list[dict[str, Any]]) -> int:
    prefix = _skills_marker_prefix()
    before = len(messages_ref)
    messages_ref[:] = [
        m
        for m in messages_ref
        if not (
            isinstance(m, dict)
            and m.get("role") == "system"
            and isinstance(m.get("content"), str)
            and m.get("content").startswith(prefix)
        )
    ]
    return before - len(messages_ref)


def _persist_messages_with_warn(
    messages: list[dict[str, Any]], *, core: Any, label: str
) -> None:
    try:
        cb = get_callbacks()
        rewrite_current_log = getattr(cb, "rewrite_current_log_from_messages", None)
        if rewrite_current_log is not None:
            rewrite_current_log(messages)
        else:
            core.rewrite_current_log_from_messages(messages)
    except Exception as e:
        import sys

        print(
            _(
                "skill.warn.rewrite_failed",
                default="[{label} warn] Failed to rewrite current log: {error}",
                label=label,
                error=f"{type(e).__name__}: {e}",
            ),
            file=sys.stderr,
        )


def make_finish_skill_handler(
    messages_ref: list[dict[str, Any]], core: Any
) -> Callable[[str], str]:
    def finish_skill(message: str) -> str:
        # Trigger background profiling before clearing skill messages
        try:
            from ..profile_manager import run_profiling_async
            run_profiling_async(messages_ref, core)
        except Exception:
            pass

        removed = _clear_skill_messages(messages_ref)
        if removed > 0:
            _persist_messages_with_warn(messages_ref, core=core, label="finish_skill")
            return json.dumps(
                {
                    "status": "ok",
                    "message": _(
                        "skill.clear_log",
                        default="{message} (Cleared {removed} skill messages)",
                        message=message,
                        removed=removed,
                    ),
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "status": "ok",
                "message": _("skill.ok", default="{message}", message=message),
            },
            ensure_ascii=False,
        )

    return finish_skill
