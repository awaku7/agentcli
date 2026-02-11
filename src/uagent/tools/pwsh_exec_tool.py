# tools/pwsh_exec_tool.py
from typing import Any, Dict
import os
import subprocess
import shutil

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:pwsh_exec"


def _probe_powershell_versions() -> Dict[str, str]:
    """Return detected PowerShell versions as strings.

    Keys may include 'pwsh' (PowerShell 7+) and/or 'powershell' (Windows PowerShell).
    """

    def probe(exe: str) -> str:
        if not shutil.which(exe):
            return ""
        try:
            # Use UTF-8 to avoid mojibake in version string.
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
        "description": "【最終手段】PowerShell を実行します。他の適切なツール（MCP等）が利用できない場合にのみ使用してください。"
        + _DESC_SUFFIX,
        "system_prompt": """このツールは【最終手段】です。
1. まず handle_mcp / mcp_tools_list で代替手段がないか確認してください。
2. 他に手段がない場合にのみ、このツールで PowerShell を実行します。
3. Python の実行には使用しないでください。代わりに python_exec ツールを使用してください。

セキュリティ注記:
- download-exec（IWR/IRM/curl/wget 等）、Base64(-Enc) 等の危険パターンは確認が入る/ブロックされます。
""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "PowerShell command string passed to -Command.",
                },
                "shell": {
                    "type": "string",
                    "description": "PowerShell executable to use: 'pwsh' (PowerShell 7+) or 'powershell' (Windows PowerShell). If omitted, auto-select.",
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

    # Default selection policy:
    # - Prefer pwsh if available
    # - Fallback to Windows PowerShell on Windows
    if shutil.which("pwsh"):
        return "pwsh"
    if os.name == "nt" and shutil.which("powershell"):
        return "powershell"
    # Last resort: return 'pwsh' (will error later with a clear message)
    return "pwsh"


# Guard helper (reuse cmd_exec guard; it already contains PS-specific patterns)
try:
    from .safe_exec_ops import decide_cmd_exec, confirm_if_needed
except Exception:
    decide_cmd_exec = None  # type: ignore[assignment]
    confirm_if_needed = None  # type: ignore[assignment]


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    command = str(args.get("command", "") or "")
    shell = _choose_shell(args.get("shell", ""))

    if not command:
        return "[pwsh_exec error] 'command' is required"

    if not shutil.which(shell):
        return f"[pwsh_exec error] PowerShell executable not found: {shell}"

    # --- Force UTF-8 in the PowerShell session to avoid mojibake ---
    # Notes:
    # - This affects only the spawned PowerShell process.
    # - We set both Console.OutputEncoding and $OutputEncoding.
    # - The tool itself decodes stdout/stderr using cb.cmd_encoding (default: utf-8).
    # - When users run under Windows PowerShell 5.1 with legacy code pages, this often fixes
    #   JSON / Japanese output corruption.
    ps_prefix = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$OutputEncoding=[System.Text.Encoding]::UTF8; "
    )
    command = ps_prefix + command

    # --- security guard ---
    if decide_cmd_exec is not None:
        decision = decide_cmd_exec(command)
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
        return f"[pwsh_exec timeout] {cb.cmd_exec_timeout_ms / 1000:.0f}秒以内に終了しませんでした"
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
