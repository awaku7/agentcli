# tools/cmd_exec.py
from typing import Any, Dict
import os
import subprocess

from .context import get_callbacks
import sys

BUSY_LABEL = True
STATUS_LABEL = "tool:cmd_exec"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cmd_exec",
        "description": "【最終手段】Windows のコマンドを実行します。他の適切なツール（MCP等）が利用できない場合にのみ使用してください。",
        "system_prompt": """このツールは【最終手段】です。
1. まず handle_mcp / mcp_tools_list で代替手段がないか確認してください。
2. 他に手段がない場合にのみ、このツールで Windows のコマンドを実行します。
3. Python の実行には使用しないでください。代わりに python_exec ツールを使用してください。

セキュリティ注記:
- 危険コマンド（破壊的削除、OS設定変更等）はブロックされます。
""",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "cmd.exe /c に渡すコマンド文字列（Windows）またはシェルに渡すコマンド（Unix）。",
                }
            },
            "required": ["command"],
        },
    },
}


# Guard helper
try:
    from .safe_exec_ops import decide_cmd_exec, confirm_if_needed
except Exception:
    decide_cmd_exec = None  # type: ignore[assignment]
    confirm_if_needed = None  # type: ignore[assignment]


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    command = str(args.get("command", "") or "")

    # Normalize python invocation on Windows for stable quoting/timeout behavior in tests.

    # If command starts with 'python -c', replace it with sys.executable.

    if os.name == "nt":

        s = command.lstrip()

        if s.lower().startswith("python -c "):

            command = sys.executable + s[len("python") :]
    # --- security guard ---
    if decide_cmd_exec is not None:
        decision = decide_cmd_exec(command)
        if not decision.allowed:
            return f"[cmd_exec blocked] {decision.reason}"
        if decision.require_confirm and confirm_if_needed is not None:
            err = confirm_if_needed(decision)
            if err is not None:
                return err

    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=cb.cmd_encoding,
            errors="replace",
            timeout=cb.cmd_exec_timeout_ms / 1000.0,
            shell=True,
        )
    except subprocess.TimeoutExpired:
        return f"[cmd_exec timeout] {cb.cmd_exec_timeout_ms / 1000:.0f}秒以内に終了しませんでした"
    except Exception as e:
        return f"[cmd_exec error] {type(e).__name__}: {e}"

    out_str = proc.stdout or ""
    err_str = proc.stderr or ""

    if proc.returncode != 0:
        msg = (
            f"[cmd_exec error] returncode={proc.returncode}\n"
            f"STDOUT:\n{out_str}\n"
            f"STDERR:\n{err_str}"
        )
        if cb.truncate_output is not None:
            return cb.truncate_output("cmd_exec", msg, 400_000)
        return msg

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += f"\n[stderr]\n{err_str}"

    if cb.truncate_output is not None:
        return cb.truncate_output("cmd_exec", out_str, 400_000)
    return out_str
