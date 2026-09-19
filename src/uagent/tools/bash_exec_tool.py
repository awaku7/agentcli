from __future__ import annotations

import os
import shlex
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


def _policy_block_reason(command: str) -> str | None:
    policy = os.environ.get("UAGENT_BASH_EXEC_POLICY", "").strip().lower()
    if policy in {"deny", "off", "disabled", "0", "false", "no"}:
        return "disabled by UAGENT_BASH_EXEC_POLICY"

    non_interactive = os.environ.get("UAGENT_NON_INTERACTIVE", "").strip().lower()
    allow = os.environ.get("UAGENT_ALLOW_BASH_EXEC", "").strip().lower()
    is_non_interactive = non_interactive in {"1", "true", "yes", "on"}
    if is_non_interactive and allow not in {"1", "true", "yes", "on"}:
        return (
            "disabled in non-interactive mode; set UAGENT_ALLOW_BASH_EXEC=1 "
            "for explicit opt-in"
        )

    raw_allowlist = os.environ.get("UAGENT_BASH_EXEC_ALLOWLIST", "")
    allowlist = {
        item.strip().lower() for item in raw_allowlist.split(",") if item.strip()
    }
    require_allowlist = os.environ.get(
        "UAGENT_BASH_EXEC_REQUIRE_ALLOWLIST", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if is_non_interactive and not allowlist:
        require_allowlist = True
    if not allowlist and require_allowlist:
        return (
            "no bash command allowlist configured; set "
            "UAGENT_BASH_EXEC_ALLOWLIST=command1,command2"
        )

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return f"command could not be parsed safely: {exc}"
    if not tokens:
        return "empty command"
    executable = os.path.basename(tokens[0]).strip().lower()
    if allowlist and executable not in allowlist:
        return (
            f"command '{executable}' is not in UAGENT_BASH_EXEC_ALLOWLIST "
            f"({','.join(sorted(allowlist))})"
        )
    return None


def run_tool(args: dict[str, Any]) -> str:
    command = str(args.get("command", "") or "")
    if not command:
        raise ValueError("command is required")

    policy_reason = _policy_block_reason(command)
    if policy_reason:
        return _(
            "err.blocked",
            default="[bash_exec blocked] %(reason)s",
        ) % {"reason": policy_reason}

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
