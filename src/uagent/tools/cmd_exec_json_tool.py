from __future__ import annotations

import json
import locale
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


def _decode_process_output(value: Any, preferred_encoding: str) -> str:
    """Decode subprocess bytes without trusting the host console code page.

    On Windows, Python child processes may emit UTF-8 while the parent locale
    still reports CP932. Prefer the configured encoding, then UTF-8, then the
    locale encoding; never let malformed output crash the reader thread.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, (bytes, bytearray)):
        return str(value)
    if not value:
        return ""

    candidates = [
        str(preferred_encoding or "utf-8"),
        "utf-8-sig",
        locale.getpreferredencoding(False) or "utf-8",
    ]
    attempted: set[str] = set()
    for encoding in candidates:
        normalized = encoding.casefold()
        if normalized in attempted:
            continue
        attempted.add(normalized)
        try:
            return bytes(value).decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return bytes(value).decode("utf-8", errors="replace")


def _command_output_encoding(
    command: str, configured_encoding: str, *, is_windows: bool
) -> str:
    """Match decoding to the encoding selected for command output."""
    if is_windows and not command.startswith(("python -c ", "python3 -c ")):
        # _run prefixes shell commands with `chcp 65001`, so their output is UTF-8
        # even if the parent process was started under a CP932 locale.
        return "utf-8"
    return str(configured_encoding or "utf-8")


def _run(
    command: str, cwd: Optional[str], timeout_ms: Optional[int] = None
) -> dict[str, Any]:
    encoding = "utf-8"
    try:
        from .context import get_callbacks

        cb = get_callbacks()
        encoding = _command_output_encoding(
            command,
            str(getattr(cb, "cmd_encoding", "utf-8") or "utf-8"),
            is_windows=os.name == "nt",
        )
        timeout_ms = timeout_ms or getattr(cb, "cmd_exec_timeout_ms", 60_000)
        timeout_sec = max(0.001, float(timeout_ms) / 1000.0)
        run_kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            # Capture bytes, then decode explicitly. TextIOWrapper can otherwise
            # raise in subprocess' reader thread when child output is UTF-8 but
            # the Windows locale encoding is CP932.
            "capture_output": True,
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

        stdout = _decode_process_output(p.stdout, encoding)
        stderr = _decode_process_output(p.stderr, encoding)
        result: dict[str, Any] = {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        if not result["ok"]:
            result["error"] = stderr.strip() or _(
                "error.exit_code", default="command exited with code %(returncode)s"
            ) % {"returncode": p.returncode}
        return result
    except subprocess.TimeoutExpired as e:
        stdout = _decode_process_output(e.stdout, encoding)
        stderr = _decode_process_output(e.stderr, encoding)
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
