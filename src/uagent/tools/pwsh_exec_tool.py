# tools/pwsh_exec_tool.py
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict
import os
import subprocess
import shutil

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:pwsh_exec"


def _probe_powershell_versions() -> Dict[str, str]:
    """Return detected PowerShell versions as strings."""

    def probe(exe: str) -> str:
        if not shutil.which(exe):
            return ""
        try:
            cmd = [
                exe,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$PSVersionTable.PSVersion.ToString()",
            ]
            r = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
            )
            out = (r.stdout or "").strip()
            if r.returncode == 0 and out:
                return out
        except Exception:
            return ""
        return ""

    vers: Dict[str, str] = {}
    v_pwsh = probe("pwsh")
    v_ps = probe("powershell")
    if v_pwsh:
        vers["pwsh"] = v_pwsh
    if v_ps:
        vers["powershell"] = v_ps
    return vers


_VERSIONS = _probe_powershell_versions()

if os.name == "nt":
    if _VERSIONS.get("pwsh") and _VERSIONS.get("powershell"):
        _DESC_SUFFIX = f" (detected: pwsh {_VERSIONS['pwsh']} / powershell {_VERSIONS['powershell']})"
    elif _VERSIONS.get("pwsh"):
        _DESC_SUFFIX = f" (detected: pwsh {_VERSIONS['pwsh']})"
    elif _VERSIONS.get("powershell"):
        _DESC_SUFFIX = f" (detected: powershell {_VERSIONS['powershell']})"
    else:
        _DESC_SUFFIX = " (PowerShell executable not found)"
else:
    if _VERSIONS.get("pwsh"):
        _DESC_SUFFIX = f" (detected: pwsh {_VERSIONS['pwsh']})"
    else:
        _DESC_SUFFIX = " (pwsh not found)"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "pwsh_exec",
        "description": _(
            "tool.description",
            default="[Last resort] Execute PowerShell. Use only when no other appropriate tool (e.g., MCP) is available.",
        )
        + _DESC_SUFFIX,
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool is a LAST RESORT.\n"
                "1. First check handle_mcp / mcp_tools_list for alternative means.\n"
                "2. Only if no other way exists, use this tool to execute PowerShell.\n"
                "3. Do not use this for Python execution. Use python_exec instead.\n\n"
                "Security Note:\n"
                "- Dangerous patterns like download-exec (IWR/IRM/curl/wget etc.) or Base64 (-Enc) will be confirmed or blocked."
            ),
        ),
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


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    command = str(args.get("command", "") or "")
    shell = _choose_shell(args.get("shell", ""))

    if not command:
        return _(
            "err.command_required", default="[pwsh_exec error] 'command' is required"
        )

    if not shutil.which(shell):
        return f"[pwsh_exec error] PowerShell executable not found: {shell}"

    ps_prefix = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$OutputEncoding=[System.Text.Encoding]::UTF8; "
    )
    command = ps_prefix + command

    if decide_cmd_exec is not None:
        decision = decide_cmd_exec(command, require_confirm_for_shell_metachar=False)
        if not decision.allowed:
            return f"[pwsh_exec blocked] {decision.reason}"
        if decision.require_confirm and confirm_if_needed is not None:
            err = confirm_if_needed(decision)
            if err is not None:
                return err.replace("cmd_exec", "pwsh_exec")

    try:
        proc = subprocess.run(
            [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=cb.cmd_encoding,
            errors="replace",
            timeout=cb.cmd_exec_timeout_ms / 1000.0,
        )
    except subprocess.TimeoutExpired:
        return _(
            "err.timeout",
            default="[pwsh_exec timeout] did not finish within {seconds} seconds",
        ).format(seconds=cb.cmd_exec_timeout_ms / 1000.0)
    except Exception as e:
        return f"[pwsh_exec error] {type(e).__name__}: {e}"

    out_str = proc.stdout or ""
    err_str = proc.stderr or ""

    if proc.returncode != 0:
        msg = (
            f"[pwsh_exec error] returncode={proc.returncode}\n"
            f"STDOUT:\n{out_str}\n"
            f"STDERR:\n{err_str}"
        )
        if cb.truncate_output is not None:
            return cb.truncate_output("pwsh_exec", msg, 400_000)
        return msg

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += f"\n[stderr]\n{err_str}"

    if cb.truncate_output is not None:
        return cb.truncate_output("pwsh_exec", out_str, 400_000)
    return out_str
