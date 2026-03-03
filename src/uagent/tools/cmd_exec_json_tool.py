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
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="Command string passed to cmd.exe /c (Windows) or sh -lc (Unix-like).",
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


def _run(command: str, cwd: Optional[str]) -> Dict[str, Any]:
    if os.name == "nt":
        # Force UTF-8 on cmd.exe
        # NOTE: Some commands may behave differently under code page 65001.
        cmd = ["cmd.exe", "/d", "/c", f"chcp 65001 >nul & {command}"]
        p = subprocess.run(
            cmd,
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
    cwd_raw = args.get("cwd", None)
    cwd = None if cwd_raw is None else str(cwd_raw)

    out = _run(command, cwd)
    return json.dumps(out, ensure_ascii=False)
