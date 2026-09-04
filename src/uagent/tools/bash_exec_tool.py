from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_exec_ops import confirm_if_needed, decide_cmd_exec

_ = make_tool_translator(__file__)

BUSY_LABEL = True

_TOOL_AVAILABLE = os.name != "nt" and bool(shutil.which("bash"))

LOAD_DISABLED_REASON = _(
    "err.unavailable",
    default="This tool is available on Unix-like systems with bash installed.",
)

TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "type": "function",
    "tool_genre": "exec",
    # Shell execution remains opt-in even when the backend is available.
    "tool_level": 1 if _TOOL_AVAILABLE else -1,
    "function": {
        "name": "bash_exec",
        "description": _(
            "tool.description",
            default=(
                "As a last resort, execute a bash command. Use only when no other appropriate tool is available."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "bash_exec",
                "bash exec",
                "bash",
                "shell command",
                "execute shell",
            ],
        ),
        "x_search_terms_en": [
            "bash_exec",
            "bash exec",
            "bash",
            "shell command",
            "execute shell",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="Command string passed to bash -lc.",
                    ),
                }
            },
            "required": ["command"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    command = str(args.get("command", "") or "")
    if not command:
        raise ValueError("command is required")

    if not _TOOL_AVAILABLE:
        return _(
            "err.unavailable",
            default="This tool is available on Unix-like systems with bash installed.",
        )

    decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=True)
    if not decision.allowed:
        return _(
            "err.blocked",
            default="[bash_exec blocked] %(reason)s",
        ) % {"reason": decision.reason}

    confirm_err = confirm_if_needed(decision)
    if confirm_err is not None:
        return confirm_err

    try:
        p = subprocess.run(
            ["bash", "-lc", command],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return _(
            "err.exception",
            default="[bash_exec error] %(type)s: %(message)s",
        ) % {"type": type(e).__name__, "message": str(e)}

    out = p.stdout or ""
    err = p.stderr or ""

    if p.returncode != 0:
        return _(
            "err.returncode",
            default="[bash_exec]\n(returncode=%(code)s)\nSTDOUT:\n%(stdout)s\nSTDERR:\n%(stderr)s",
        ) % {
            "code": p.returncode,
            "stdout": out,
            "stderr": err,
        }

    return "[bash_exec]\n" + out
