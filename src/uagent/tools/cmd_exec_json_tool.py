# tools/cmd_exec_json_tool.py
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cmd_exec_json",
        "description": _(
            "tool.description",
            default=(
                "As a last resort, execute a command and return JSON. Use only when no other appropriate tool (e.g., MCP) is available."
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
                },
                "cwd": {
                    "description": _(
                        "param.cwd.description",
                        default=(
                            "Working directory (only relative paths under workdir are allowed). If null, uses current."
                        ),
                    ),
                },
            },
            "required": ["command"],
        },
    },
}


def _run(command: str, cwd: Optional[str]) -> Dict[str, Any]:
    if os.name == "nt":
        cmd = ["cmd.exe", "/c", command]
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
    cwd_raw = args.get("cwd", None)
    cwd = None if cwd_raw is None else str(cwd_raw)

    out = _run(command, cwd)
    return json.dumps(out, ensure_ascii=False)
