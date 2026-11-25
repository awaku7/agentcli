"""Security guard helpers for command execution.

Policy (B: medium):
- Block obviously destructive commands.
- Require explicit human confirmation for risky patterns (download-exec, encoded payloads,
  shell chaining/redirection, etc.).

Confirmation:
- Use the host's shared ToolPolicy -> human_ask approval path.
- If interaction is unavailable, reject without falling back to raw input().

Cancellation:
- User can cancel by replying 'c' or 'cancel'.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


class SubprocessInterrupted(Exception):
    """The user interrupt flag stopped a subprocess wait."""


def _interrupt_requested() -> bool:
    try:
        from .. import core

        return bool(getattr(core, "interrupt_requested", False))
    except Exception:
        return False


def run_interruptible(**run_kwargs: Any) -> subprocess.CompletedProcess:
    """``subprocess.run()`` that also honours the user interrupt flag.

    Command execution used to be released by KeyboardInterrupt reaching
    the wait on the main thread; rounds now run on worker threads that
    never see it, and the Windows exec tools deliberately start their
    children in a separate process group, so the console signal does
    not reach them either.  Poll the child in short slices instead:
    when an interrupt is requested, kill the child and raise
    SubprocessInterrupted so the caller can return its interrupted
    result.  Timeout handling matches subprocess.run(): the child is
    killed and TimeoutExpired is raised with the output collected.
    """
    timeout = run_kwargs.pop("timeout", None)
    check = bool(run_kwargs.pop("check", False))
    if run_kwargs.pop("capture_output", False):
        # capture_output is a subprocess.run() convenience; Popen wants
        # the explicit pipes (same translation run() performs).
        if "stdout" in run_kwargs or "stderr" in run_kwargs:
            raise ValueError
        run_kwargs["stdout"] = subprocess.PIPE
        run_kwargs["stderr"] = subprocess.PIPE
    proc = subprocess.Popen(**run_kwargs)
    deadline = None if timeout is None else time.monotonic() + float(timeout)
    out: Any = None
    err: Any = None
    while True:
        slice_timeout = 0.2
        if deadline is not None:
            slice_timeout = min(slice_timeout, max(0.0, deadline - time.monotonic()))
        try:
            out, err = proc.communicate(timeout=slice_timeout)
            break
        except subprocess.TimeoutExpired:
            if _interrupt_requested():
                proc.kill()
                proc.wait()
                raise SubprocessInterrupted() from None
            if deadline is not None and time.monotonic() >= deadline:
                proc.kill()
                out, err = proc.communicate()
                raise subprocess.TimeoutExpired(
                    proc.args, float(timeout or 0.0), output=out, stderr=err
                ) from None
    result = subprocess.CompletedProcess(proc.args, proc.returncode, out, err)
    if check:
        result.check_returncode()
    return result


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


def decide_cmd_exec(
    command: str, *, require_confirm_for_shell_metachar: bool = True
) -> ExecDecision:
    cmd_norm = _normalize_cmd(command)
    if not cmd_norm:
        return ExecDecision(False, _("err.empty_command", default="empty command"))

    block_list = _WIN_BLOCK if _is_windows() else _POSIX_BLOCK
    for pat in block_list:
        if re.search(pat, cmd_norm):
            return ExecDecision(
                False,
                _("err.blocked_by_rule", default="blocked by rule: {pattern}").format(
                    pattern=pat
                ),
            )

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

    if require_confirm_for_shell_metachar:
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
    """Return None only when the common host confirmation approves."""
    from .tool_confirmation import active_tool_name, confirm_operation

    tool_name = active_tool_name() or "cmd_exec"
    if confirm_operation(message, tool_name=tool_name):
        return None
    return _("err.blocked_rejected", default="user rejected")


def confirm_if_needed(decision: ExecDecision) -> Optional[str]:
    """Return error string when not confirmed; None when ok."""
    if not decision.require_confirm:
        return None

    return _human_ask_confirm(decision.confirm_message)
