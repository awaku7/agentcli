from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional

from .i18n_helper import make_tool_translator
from .safe_exec_ops import confirm_if_needed, decide_cmd_exec
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cmd_exec_json",
        "description": _(
            "tool.description",
            default=(
                "As a last resort, execute a shell command and return a JSON result. "
                "Use only when no safer or more specific tool is available (e.g., an MCP integration)."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is a LAST RESORT. Use it only if no other appropriate tool is available. "
                "Be conservative with commands and avoid destructive operations unless explicitly confirmed by the user."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "cmd_exec_json",
                "cmd exec json",
                "shell command",
                "execute shell",
                "json command",
                "cmd",
            ],
        ),
        "x_search_terms_en": [
            "cmd_exec_json",
            "cmd exec json",
            "shell command",
            "execute shell",
            "json command",
            "cmd",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="Command string passed to the OS shell. On Windows, cmd.exe /c is used.",
                    ),
                },
                "cwd": {
                    "type": ["string", "null"],
                    "description": _(
                        "param.cwd.description",
                        default=(
                            "Working directory. Only relative paths under workdir are allowed. If null, uses the current directory."
                        ),
                    ),
                },
            },
            "required": ["command"],
        },
    },
}


def _blocked_result(reason: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "blocked": True,
        "reason": reason,
        "error": reason,
        "returncode": 1,
        "stdout": "",
        "stderr": "",
    }


def _run(command: str, cwd: Optional[str]) -> Dict[str, Any]:
    if os.name == "nt":
        # Force UTF-8 on cmd.exe.
        # Use a shell command string instead of ["cmd.exe", "/c", command].
        # Passing /c as a list argument makes Python quote the whole command
        # line for CreateProcess; embedded quotes then get misparsed by cmd.exe
        # (for example: python -c "..." or pytest -k "a or b").
        p = subprocess.run(
            f"chcp 65001 >nul & {command}",
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
        )
    else:
        cmd = ["sh", "-lc", command]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

    return {
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def run_tool(args: Dict[str, Any]) -> str:
    command = str(args.get("command", "") or "")
    if not command:
        raise ValueError("command is required")

    decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=True)
    if not decision.allowed:
        return json.dumps(_blocked_result(decision.reason), ensure_ascii=False)

    confirm_err = confirm_if_needed(decision)
    if confirm_err is not None:
        return json.dumps(_blocked_result(confirm_err), ensure_ascii=False)

    cwd_raw = args.get("cwd", None)
    if cwd_raw is None:
        cwd = None
    elif not isinstance(cwd_raw, str):
        raise ValueError("cwd must be a string or null")
    else:
        cwd = ensure_within_workdir(cwd_raw)

    out = _run(command, cwd)
    return json.dumps(out, ensure_ascii=False)
