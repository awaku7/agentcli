# tools/cmd_exec_tool.py
from __future__ import annotations

import os
import subprocess
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cmd_exec",
        "description": _(
            "tool.description",
            default=(
                "As a last resort, execute a Windows command. Use only when no other appropriate tool (e.g., MCP) is available."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is a LAST RESORT. Use only if no other appropriate tool is available."
            ),
        ),
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


def run_tool(args: Dict[str, Any]) -> str:
    command = str(args.get("command", "") or "")
    if not command:
        raise ValueError("command is required")

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
