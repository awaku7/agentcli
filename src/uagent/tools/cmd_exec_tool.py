# tools/cmd_exec_tool.py
from __future__ import annotations

import os
import subprocess
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_exec_ops import confirm_if_needed, decide_cmd_exec

_ = make_tool_translator(__file__)

BUSY_LABEL = True
LOAD_DISABLED_REASON = "This tool is available on Windows only."

TOOL_SPEC: dict[str, Any] = {
    # Optional tool gating:
    # -1 = disabled (will not be registered/loaded)
    "tool_level": 0 if os.name == "nt" else -1,
    "type": "function",
    "tool_genre": "exec",
    "function": {
        "name": "cmd_exec",
        "description": _(
            "tool.description",
            default=(
                "As a last resort, execute a Windows command. Use only when no other appropriate tool (e.g., MCP) is available."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "cmd_exec",
                "cmd exec",
                "windows command",
                "command prompt",
                "cmd",
                "shell command",
            ],
        ),
        "x_search_terms_en": [
            "cmd_exec",
            "cmd exec",
            "windows command",
            "command prompt",
            "cmd",
            "shell command",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default=(
                            "Command string passed to cmd.exe /c (Windows) or the shell (Unix)."
                        ),
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

    decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=False)
    if not decision.allowed:
        return f"[cmd_exec blocked] {decision.reason}"

    confirm_err = confirm_if_needed(decision)
    if confirm_err is not None:
        return f"[cmd_exec blocked] {confirm_err}"

    # Keep behavior close to legacy: use cmd.exe on Windows.
    if os.name == "nt":
        cmd = ["cmd.exe", "/c", command]
    else:
        cmd = ["sh", "-lc", command]

    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout
    err = p.stderr

    if p.returncode != 0:
        return (
            f"[cmd_exec]\n(returncode={p.returncode})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
        )

    return f"[cmd_exec]\n{out}"
