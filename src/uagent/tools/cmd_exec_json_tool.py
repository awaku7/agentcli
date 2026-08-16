from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any, Optional

from .i18n_helper import make_tool_translator
from .safe_exec_ops import confirm_if_needed, decide_cmd_exec
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "type": "function",
    "tool_genre": "exec",
    "function": {
        "name": "cmd_exec_json",
        "description": _(
            "tool.description",
            default="As a last resort, execute a shell command and return a JSON result. Use only when no safer or more specific tool is available (e.",
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
                    "type": "string",
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


def _blocked_result(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "blocked": True,
        "reason": reason,
        "error": reason,
        "returncode": 1,
        "stdout": "",
        "stderr": "",
    }


def _run(command: str, cwd: Optional[str]) -> dict[str, Any]:
    try:
        if os.name == "nt":
            if command.startswith(("python -c ", "python3 -c ")):
                parts = shlex.split(command)
                p = subprocess.run(
                    parts,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=cwd,
                )
            else:
                p = subprocess.run(
                    f"chcp 65001 >nul & {command}",
                    shell=True,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=cwd,
                )
        else:
            cmd = ["sh", "-lc", command]
            p = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                cwd=cwd,
            )

        result: dict[str, Any] = {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
        if not result["ok"]:
            result["error"] = (p.stderr or "").strip() or _(
                "error.exit_code", default="command exited with code %(returncode)s"
            ) % {"returncode": p.returncode}
        return result
    except OSError as e:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "error": _(
                "error.os_error",
                default="command execution failed (OS error): %(error)s",
            )
            % {"error": str(e)},
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "error": _(
                "error.exec_failed",
                default="command execution failed: %(error)s",
            )
            % {"error": str(e)},
        }


def run_tool(args: dict[str, Any]) -> str:
    command = str(args.get("command", "") or "")
    if not command:
        raise ValueError("command is required")

    decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=False)
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
    elif cwd_raw.strip() == "":
        cwd = None
    else:
        cwd = ensure_within_workdir(cwd_raw)

    out = _run(command, cwd)
    return json.dumps(out, ensure_ascii=False)
