"""Status / prompt / env helpers (split from core.py)."""

from __future__ import annotations

import os
from typing import Optional

from ..env_utils import env_get, strip_outer_quotes
from ..i18n import _
from .. import core as _core
from .display import print_status_line


def get_computer_use_policy():
    """Return the shared Computer Use policy for the current process.

    The policy is resolved lazily so CLI/GUI/Web/A2A startup code can load its
    environment configuration before requesting it.
    """
    from ..computer_use.config import computer_use_policy_from_env

    return computer_use_policy_from_env()


def normalize_status_label(busy: bool, label: str = "") -> str:
    """Compatibility shim for the runtime status module."""
    from ..runtime.status import normalize_status_label as _normalize

    return _normalize(busy, label)


def set_status(busy: bool, label: str = "") -> None:
    """
    Update the Busy/Idle state and draw the status line if there are changes.
    """

    # Tool implementations historically clear their own status in finally
    # blocks. During a centralized tool call, suppress that transient IDLE
    # transition so the input prompt cannot appear before the LLM resumes.
    if not busy and not getattr(_core, "human_ask_active", False):
        try:
            from ..runtime.execution import tool_runner_active

            if tool_runner_active():
                return
        except Exception:
            pass

    # Keep CLI, GUI, and Web status labels consistent.
    label = normalize_status_label(busy, label)

    # Clear on user/command input so toggling reasoning off does not leave stale
    # labels in the next prompt.
    if busy and label in (
        "command_pending",
        "user_pending",
        "user_pending_multi",
        "replying",
        "replying_cancel",
        "replying_multi",
    ):
        _core.last_reasoning_label = ""

    # If a new LLM cycle starts, clear last reasoning label.
    # It will be re-set only when we actually see an effort-bearing label.
    if busy and label in ("LLM", "LLM:auto", "LLM:auto->"):
        _core.last_reasoning_label = ""
    # Record selected effort labels when present.
    # Only keep auto-selected effort in the prompt (LLM:auto->...).
    if busy and isinstance(label, str):
        if label.startswith("LLM:auto->"):
            _core.last_reasoning_label = label
        elif label.startswith("LLM:"):
            # Explicit (non-auto) reasoning effort should not appear in the prompt.
            _core.last_reasoning_label = ""

    with _core.status_lock:
        prev_busy = _core.status_busy
        prev_label = _core.status_label
        _core.status_busy = busy
        _core.status_label = label

    if busy != prev_busy or label != prev_label:
        # In the interactive CLI, the next input prompt is the idle indicator.
        # Avoid emitting a redundant IDLE line after the assistant response;
        # that line can race with prompt redraw and appear as
        # `agentcli> [STATE] IDLE`. GUI/Web frontends retain their own status.
        is_web = bool(getattr(_core, "_is_web", False))
        if busy or bool(getattr(_core, "IS_GUI", False)) or is_web:
            print_status_line()


def get_prompt() -> str:
    """
    Return the prompt string for standard input based on the current status.
    - Idle:  [IDLE] >
    - Busy:  [BUSY:LLM] > or similar
    """
    with _core.status_lock:
        busy = _core.status_busy
        label = _core.status_label

    with _core.human_ask_lock:
        ask_active = _core.human_ask_active

    if ask_active:
        # Re-check under lock to avoid race with human_ask_tool.run_tool() finally block
        # that sets human_ask_active = False. Without this re-check, a stale [REPLY] prompt
        # may be displayed after the user has already replied.
        with _core.human_ask_lock:
            if _core.human_ask_active:
                return "[REPLY] > "
        ask_active = False

    if _core.auto_pilot_active:
        return "[AUTO] > "

    from ..runtime.prompt_context import format_prompt

    try:
        cwd = os.getcwd()
    except Exception:
        cwd = "?"
    base = os.path.basename(cwd.rstrip(os.sep)) or cwd
    with _core.status_lock:
        _lr = _core.last_reasoning_label
    return format_prompt(busy=busy, label=label, cwd_name=base, reasoning_label=_lr)


def get_env(name: str) -> str:
    value = env_get(name)
    if not value:
        raise ValueError(
            _("Environment variable %(name)s is not set.") % {"name": name}
        )
    return value


def normalize_url(url: str) -> str:
    if not url:
        return ""
    # Also accept quoted env values: "https://..." or 'https://...'
    url2 = strip_outer_quotes(str(url))
    return url2.strip().rstrip("/")


def get_env_url(name: str, default: Optional[str] = None) -> str:
    val = env_get(name, default)
    if not val:
        if default is not None:
            return normalize_url(default)
        raise ValueError(
            _("Environment variable %(name)s is not set.") % {"name": name}
        )
    return normalize_url(val)


def truncate_output(
    label: str, text: str, limit: int = _core.MAX_TOOL_OUTPUT_CHARS
) -> str:
    """Compatibility shim for runtime.history."""
    from ..runtime.history import truncate_output as _truncate

    return _truncate(label, text, limit)
