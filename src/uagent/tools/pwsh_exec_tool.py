from __future__ import annotations

# tools/pwsh_exec_tool.py
from .i18n_helper import make_tool_translator
from ..runtime.tool_execution_result import ToolExecutionText

_ = make_tool_translator(__file__)

from typing import Any
import os
import subprocess
import shutil

from .context import get_callbacks

BUSY_LABEL = True
LOAD_DISABLED_REASON = "This tool is available on Windows only."
STATUS_LABEL = "tool:pwsh_exec"


def _detect_powershell_executables() -> dict[str, bool]:
    """Return which PowerShell executables are on PATH.

    This runs at import time (the result is baked into the tool description),
    so it must stay cheap: only a PATH lookup, never a subprocess. Launching
    PowerShell to read ``$PSVersionTable`` here cost ~0.5 s on every first
    tool access.
    """
    return {
        "pwsh": bool(shutil.which("pwsh")),
        "powershell": bool(shutil.which("powershell")),
    }


def _describe_detected(found: dict[str, bool]) -> str:
    # Suffix of the LLM-facing tool description (kept in English, as before).
    if os.name == "nt":
        if found.get("pwsh") and found.get("powershell"):
            suffix = " (detected: pwsh / powershell)"
        elif found.get("pwsh"):
            suffix = " (detected: pwsh)"
        elif found.get("powershell"):
            suffix = " (detected: powershell)"
        else:
            suffix = " (PowerShell executable not found)"
    elif found.get("pwsh"):
        suffix = " (detected: pwsh)"
    else:
        suffix = " (pwsh not found)"
    return suffix


_DESC_SUFFIX = _describe_detected(_detect_powershell_executables())


TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "type": "function",
    "tool_level": -1,
    "function": {
        "name": "pwsh_exec",
        "description": _(
            "tool.description",
            default=(
                "Last resort: run a PowerShell command. Use only when no more "
                "appropriate tool (MCP, etc.) is available."
            ),
        )
        + _DESC_SUFFIX,
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "pwsh_exec",
                "pwsh exec",
            ],
        ),
        "x_search_terms_en": [
            "pwsh_exec",
            "pwsh exec",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": _(
                        "param.command.description",
                        default="PowerShell command string passed to -Command.",
                    ),
                },
                "shell": {
                    "type": "string",
                    "description": _(
                        "param.shell.description",
                        default="PowerShell executable to use: 'pwsh' (PowerShell 7+) or 'powershell' (Windows PowerShell). If omitted, auto-select.",
                    ),
                    "enum": ["pwsh", "powershell"],
                },
            },
            "required": ["command"],
        },
    },
}


def _choose_shell(requested: str = "") -> str:
    requested = (requested or "").strip().lower()
    if requested in ("pwsh", "powershell"):
        return requested

    if shutil.which("pwsh"):
        return "pwsh"
    if os.name == "nt" and shutil.which("powershell"):
        return "powershell"
    return "pwsh"


try:
    from .safe_exec_ops import confirm_if_needed, decide_cmd_exec
except Exception:
    decide_cmd_exec = None  # type: ignore[assignment]
    confirm_if_needed = None  # type: ignore[assignment]


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()

    command = str(args.get("command", "") or "")
    shell = _choose_shell(args.get("shell", ""))

    if not command:
        return _(
            "err.command_required", default="[pwsh_exec error] 'command' is required"
        )

    if not shutil.which(shell):
        return _(
            "err.shell_not_found",
            default="[pwsh_exec error] PowerShell executable not found: %(shell)s",
        ) % {"shell": shell}

    ps_prefix = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$OutputEncoding=[System.Text.Encoding]::UTF8; "
    )
    command = ps_prefix + command

    if decide_cmd_exec is not None:
        decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=False)
        if not decision.allowed:
            return _(
                "err.blocked",
                default="[pwsh_exec blocked] %(reason)s",
            ) % {"reason": decision.reason}
        if decision.require_confirm and confirm_if_needed is not None:
            err = confirm_if_needed(decision)
            if err is not None:
                return err

    # Do not inherit the host stdin. Interactive CLI treats empty readline as EOF
    # and exits; a child PowerShell that shares stdin can trigger that path.
    run_kwargs: dict[str, Any] = {
        "args": [
            shell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": cb.cmd_encoding,
        "errors": "replace",
        "timeout": cb.cmd_exec_timeout_ms / 1000.0,
    }
    if os.name == "nt":
        # Do not let the PowerShell child share the CLI's console control
        # signal group. In particular, an occasionally delivered Ctrl+C can
        # otherwise be observed by both processes and make the host look as if
        # it exited silently. CREATE_NO_WINDOW is additive: stdout/stderr are
        # already pipes, so the child has no reason to own a console window.
        create_new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        creationflags = create_new_process_group | create_no_window
        if creationflags:
            run_kwargs["creationflags"] = creationflags

    try:
        proc = subprocess.run(**run_kwargs)
    except subprocess.TimeoutExpired:
        return _(
            "err.timeout",
            default="[pwsh_exec timeout] did not finish within %(seconds)s seconds",
        ) % {"seconds": cb.cmd_exec_timeout_ms / 1000.0}
    except KeyboardInterrupt:
        # subprocess.run can propagate the console interrupt to the parent
        # while it is waiting for the child. A tool must return a result, not
        # terminate the agent process, so convert it to an explicit response.
        return _(
            "err.interrupted",
            default="[pwsh_exec interrupted] PowerShell command was interrupted",
        )
    except Exception as e:
        return _(
            "err.exception",
            default="[pwsh_exec error] %(type)s: %(message)s",
        ) % {"type": type(e).__name__, "message": str(e)}

    out_str = proc.stdout or ""
    err_str = proc.stderr or ""

    if proc.returncode != 0:
        msg = _(
            "err.returncode",
            default="[pwsh_exec error] returncode=%(code)s\nSTDOUT:\n%(stdout)s\nSTDERR:\n%(stderr)s",
        ) % {
            "code": proc.returncode,
            "stdout": out_str,
            "stderr": err_str,
        }
        if cb.truncate_output is not None:
            return ToolExecutionText(
                cb.truncate_output("pwsh_exec", msg, 400_000), status="failed"
            )
        return msg

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += f"\n[stderr]\n{err_str}"

    if cb.truncate_output is not None:
        return ToolExecutionText(cb.truncate_output("pwsh_exec", out_str, 400_000))
    return ToolExecutionText(out_str)
