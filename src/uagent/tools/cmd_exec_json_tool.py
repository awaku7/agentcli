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


def _run(
    command: str, cwd: Optional[str], timeout_ms: Optional[int] = None
) -> dict[str, Any]:
    try:
        from .context import get_callbacks

        cb = get_callbacks()
        timeout_ms = timeout_ms or getattr(cb, "cmd_exec_timeout_ms", 60_000)
        timeout_sec = max(0.001, float(timeout_ms) / 1000.0)
        run_kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "capture_output": True,
            "text": True,
            "encoding": getattr(cb, "cmd_encoding", "utf-8"),
            "errors": "replace",
            "cwd": cwd,
            "timeout": timeout_sec,
        }

        if os.name == "nt":
            create_new_process_group = getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            creationflags = create_new_process_group | create_no_window
            if creationflags:
                run_kwargs["creationflags"] = creationflags

            if command.startswith(("python -c ", "python3 -c ")):
                parts = shlex.split(command)
                run_kwargs["args"] = parts
                run_kwargs["shell"] = False
                p = subprocess.run(**run_kwargs)
            else:
                run_kwargs["args"] = f"chcp 65001 >nul & {command}"
                run_kwargs["shell"] = True
                p = subprocess.run(**run_kwargs)
        else:
            run_kwargs["args"] = ["sh", "-lc", command]
            p = subprocess.run(**run_kwargs)

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
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        encoding = getattr(get_callbacks(), "cmd_encoding", "utf-8")
        if isinstance(stdout, bytes):
            stdout = stdout.decode(encoding, errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(encoding, errors="replace")
        return {
            "ok": False,
            "timeout": True,
            "returncode": 124,
            "stdout": stdout,
            "stderr": stderr,
            "error": _(
                "error.timeout",
                default="command did not finish within %(seconds)s seconds",
            )
            % {"seconds": e.timeout},
        }
    except KeyboardInterrupt:
        return {
            "ok": False,
            "interrupted": True,
            "returncode": 130,
            "stdout": "",
            "stderr": "",
            "error": _(
                "error.interrupted",
                default="command execution was interrupted",
            ),
        }
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

    timeout_override = args.get("_timeout_ms")
    if timeout_override is not None:
        try:
            timeout_override = max(1, int(timeout_override))
        except (TypeError, ValueError):
            raise ValueError("_timeout_ms must be an integer")
    out = _run(command, cwd, timeout_ms=timeout_override)
    return json.dumps(out, ensure_ascii=False)
