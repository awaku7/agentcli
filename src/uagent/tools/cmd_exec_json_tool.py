# tools/cmd_exec_json_tool.py
"""cmd_exec_json_tool

cmd_exec の JSON 版。

背景:
- 既存の cmd_exec_tool は人間向けの文字列を返し、returncode/stdout/stderr を
  構造化して返さない。
- apply_patch/run_tests/lint_format などは returncode で成否判定し、stdout/stderr を
  分離して扱いたい。

本ツールは:
- safe_exec_ops の判定・確認フローを利用
- subprocess.run の結果を JSON で返す
- 任意で cwd を指定可能（workdir 配下の相対パスのみ許可）

出力(JSON):
{
  "ok": true,
  "returncode": 0,
  "stdout": "...",
  "stderr": "..."
}

注意:
- Windows は cmd.exe /c で実行
- 非Windows は shell=True で実行（既存 cmd_exec_tool に合わせる）
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:cmd_exec_json"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "cmd_exec_json",
        "description": "【最終手段】コマンドを実行し、JSON で返します。他の適切なツール（MCP等）が利用できない場合にのみ使用してください。",
        "system_prompt": """このツールは【最終手段】です。
1. まず handle_mcp / mcp_tools_list で代替手段がないか確認してください。
2. 他に手段がない場合にのみ、このツールでコマンドを実行します。
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
                },
                "cwd": {
                    "type": ["string", "null"],
                    "description": "実行ディレクトリ（workdir配下の相対パスのみ許可）。null なら現在。",
                    "default": None,
                },
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


def _is_path_dangerous(p: str) -> bool:
    # safe_file_ops と同じ基準（簡易版）
    if not p:
        return True
    if ".." in str(p).replace("\\", "/"):
        return True
    try:
        from pathlib import Path

        if Path(p).is_absolute():
            return True
    except Exception:
        return True
    return False


def _ensure_within_workdir(p: str) -> str:
    from pathlib import Path

    root = Path(os.getcwd()).resolve()
    resolved = Path(p).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except Exception:
        raise PermissionError(f"cwd is outside workdir: root={root} cwd={resolved}")
    return str(resolved)


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    command = str(args.get("command", "") or "")
    cwd_raw = args.get("cwd", None)

    # --- security guard ---
    if decide_cmd_exec is not None:
        decision = decide_cmd_exec(command)
        if not decision.allowed:
            return json.dumps(
                {"ok": False, "blocked": True, "reason": decision.reason},
                ensure_ascii=False,
            )
        if decision.require_confirm and confirm_if_needed is not None:
            err = confirm_if_needed(decision)
            if err is not None:
                return json.dumps(
                    {"ok": False, "blocked": True, "reason": err},
                    ensure_ascii=False,
                )

    run_cwd: Optional[str] = None
    if cwd_raw is not None:
        cwd_s = str(cwd_raw)
        if _is_path_dangerous(cwd_s):
            return json.dumps(
                {"ok": False, "error": f"dangerous cwd rejected: {cwd_s}"},
                ensure_ascii=False,
            )
        try:
            run_cwd = _ensure_within_workdir(cwd_s)
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"cwd not allowed: {type(e).__name__}: {e}"},
                ensure_ascii=False,
            )

    try:
        proc = subprocess.run(
            ["cmd.exe", "/c", command] if os.name == "nt" else command,
            cwd=run_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=cb.cmd_encoding,
            errors="replace",
            timeout=cb.cmd_exec_timeout_ms / 1000.0,
            shell=(os.name != "nt"),
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "ok": False,
                "timeout": True,
                "message": f"timeout: {cb.cmd_exec_timeout_ms / 1000:.0f}s",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps(
            {"ok": False, "error": f"{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    out_str = proc.stdout or ""
    err_str = proc.stderr or ""

    # truncate if available
    if cb.truncate_output is not None:
        out_str = cb.truncate_output("cmd_exec_json stdout", out_str, 400_000)
        err_str = cb.truncate_output("cmd_exec_json stderr", err_str, 400_000)

    return json.dumps(
        {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": out_str,
            "stderr": err_str,
        },
        ensure_ascii=False,
    )
