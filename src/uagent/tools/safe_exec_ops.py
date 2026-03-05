"""Security guard helpers for command execution.

Policy (B: medium):
- Block obviously destructive commands.
- Require explicit human confirmation for risky patterns (download-exec, encoded payloads,
  shell chaining/redirection, etc.).

Confirmation:
- Prefer the host's human_ask shared-queue mechanism.
- If another human_ask is active, wait for a short time before starting confirmation.
- If callbacks are not available, fall back to input().

Cancellation:
- User can cancel by replying 'c' or 'cancel'.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


@dataclass(frozen=True)
class ExecDecision:
    allowed: bool
    reason: str
    require_confirm: bool = False
    confirm_message: str = ""


def _is_windows() -> bool:
    return os.name == "nt"


def _normalize_cmd(cmd: str) -> str:
    return re.sub(r"\s+", " ", (cmd or "").strip()).lower()


_WIN_BLOCK = [
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\breg\s+(add|delete)\b",
    r"\bbcdedit\b",
    r"\bvssadmin\b",
    r"\bwmic\b",
    r"\bsc\s+(create|delete|config|start|stop)\b",
    r"\bnet\s+user\b",
    r"\bnet\s+localgroup\b",
    r"\bnet\s+share\b",
    r"\bicacls\b",
    r"\btakeown\b",
    r"\bdel\b.*\s/\s*s\b",
    r"\bdel\b.*\s/\s*q\b",
    r"\brmdir\b.*\s/\s*s\b",
    r"\brd\b.*\s/\s*s\b",
]

_POSIX_BLOCK = [
    r"\brm\b\s+.*-rf\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bsystemctl\b\s+(stop|disable|mask)\b",
]

_CONFIRM_PATTERNS = [
    r"\bcurl\b",
    r"\bwget\b",
    r"\binvoke-webrequest\b",
    r"\biwr\b",
    r"\birm\b",
    r"\bpowershell\b.*-enc\b",
    r"\bpwsh\b.*-enc\b",
    r"\bcertutil\b.*-urlcache\b",
    r"\bbitsadmin\b",
]

_META_CONFIRM = [
    r"\|\|",
    r"\|",
    r">>",
    r">",
]


def decide_cmd_exec(command: str) -> ExecDecision:
    cmd_norm = _normalize_cmd(command)
    if not cmd_norm:
        return ExecDecision(False, _("err.empty_command", default="empty command"))

    block_list = _WIN_BLOCK if _is_windows() else _POSIX_BLOCK
    for pat in block_list:
        if re.search(pat, cmd_norm):
            return ExecDecision(False, _("err.blocked_by_rule", default="blocked by rule: {pattern}").format(pattern=pat))

    for pat in _CONFIRM_PATTERNS:
        if re.search(pat, cmd_norm):
            msg = _(
                "confirm.risky_command",
                default=(
                    "A potentially high-risk command pattern was detected.\n"
                    "command: {command}\n"
                    "Reply with y to proceed, or c to cancel."
                ),
            ).format(command=command)
            return ExecDecision(
                True,
                f"risky pattern (confirm): {pat}",
                require_confirm=True,
                confirm_message=msg,
            )

    for token_pat in _META_CONFIRM:
        if re.search(token_pat, command):
            msg = _(
                "confirm.shell_metachar",
                default=(
                    "Shell chaining/redirection operators were detected.\n"
                    "command: {command}\n"
                    "Reply with y to proceed, or c to cancel."
                ),
            ).format(command=command)
            return ExecDecision(
                True,
                f"shell metachar (confirm): {token_pat}",
                require_confirm=True,
                confirm_message=msg,
            )

    return ExecDecision(True, _("msg.allowed", default="allowed"))


def _human_ask_confirm(message: str) -> Optional[str]:
    """Ask for confirmation via the host human_ask shared queue.

    Returns:
      None when confirmed.
      error string when rejected/cancelled.
    """
    cb = get_callbacks()

    # If callbacks are not set, caller may fallback.
    if (
        cb.human_ask_lock is None
        or cb.human_ask_active_ref is None
        or cb.human_ask_set_active is None
        or cb.human_ask_queue_ref is None
        or cb.human_ask_set_queue is None
        or cb.human_ask_lines_ref is None
        or cb.human_ask_set_multiline_active is None
    ):
        return _("err.callbacks_unavailable", default="human_ask callbacks not available")

    import queue as _queue

    local_q: "_queue.Queue[str]" = _queue.Queue()

    # Wait until no other human_ask is active.
    wait_timeout_sec = 30.0
    poll_interval_sec = 0.1
    start = time.time()

    while True:
        with cb.human_ask_lock:
            busy = cb.human_ask_active_ref()
            if not busy:
                cb.human_ask_set_active(True)
                cb.human_ask_set_queue(local_q)

                lines = cb.human_ask_lines_ref()
                try:
                    lines.clear()
                except Exception:
                    pass

                cb.human_ask_set_multiline_active(False)
                break

        if time.time() - start > wait_timeout_sec:
            return _("err.confirm_timeout", default="confirmation timeout")
        time.sleep(poll_interval_sec)

    try:
        print(
            "\n" + _("ui.confirm.title", default="=== Human confirmation request ==="),
            flush=True,
        )
        print(message, flush=True)
        print(_("ui.confirm.footer", default="=== /confirm ===\n"), flush=True)
        print(
            _(
                "ui.confirm.howto",
                default="How to reply: y=proceed / c=cancel / other=deny\n",
            ),
            flush=True,
        )

        user_reply = local_q.get()
    finally:
        with cb.human_ask_lock:
            cb.human_ask_set_active(False)
            cb.human_ask_set_queue(None)
            cb.human_ask_set_multiline_active(False)

    ur = (user_reply or "").strip().lower()
    if ur == "y":
        return None
    if ur in ("c", "cancel"):
        return _("err.blocked_cancelled", default="user cancelled")
    return _("err.blocked_rejected", default="user rejected")


def confirm_if_needed(decision: ExecDecision) -> Optional[str]:
    """Return error string when not confirmed; None when ok."""
    if not decision.require_confirm:
        return None

    # Prefer host human_ask
    err = _human_ask_confirm(decision.confirm_message)
    if err is None:
        return None

    # If human_ask isn't available, fallback to input()
    if err == _("err.callbacks_unavailable", default="human_ask callbacks not available"):

        try:
            resp = input(decision.confirm_message + _("ui.fallback_prompt", default=" [y/c/N]: "))
        except Exception:
            return _("err.confirm_failed", default="confirmation failed")

        r = resp.strip().lower()
        if r == "y":
            return None
        if r in ("c", "cancel"):
            return _("err.blocked_cancelled", default="user cancelled")
        return _("err.blocked_rejected", default="user rejected")

    return err
