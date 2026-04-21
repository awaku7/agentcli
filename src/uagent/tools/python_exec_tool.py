from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import os
import subprocess
import sys
import tempfile
from typing import Any, Dict

from .context import get_callbacks

BUSY_LABEL = True
STATUS_LABEL = "tool:python_exec"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "python_exec",
        "description": _(
            "tool.description",
            default=(
                "Execute Python code in a controlled way. Use this tool for calculations, data processing, or running short scripts."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Execute Python code in a controlled way. When you are about to run code, briefly state what will be executed."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": _(
                        "param.code.description",
                        default="Python code to execute (single-line or multi-line).",
                    ),
                },
            },
            "required": ["code"],
        },
    },
}


def _run_python_code(args: Dict[str, Any], cb: Any) -> str:
    code = args.get("code", "")
    if not isinstance(code, str):
        code = str(code)

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(code)
            tmp_path = tf.name

        proc = subprocess.run(
            [sys.executable, tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=(cb.cmd_encoding or "utf-8"),
            errors="replace",
            timeout=cb.python_exec_timeout_ms / 1000.0,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return (
            f"[python_exec timeout] Did not finish within {cb.python_exec_timeout_ms / 1000:.0f} seconds"
        )
    except Exception as e:
        return f"[python_exec error] {type(e).__name__}: {e}"
    finally:
        try:
            if "tmp_path" in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    out_str = proc.stdout or ""
    err_str = proc.stderr or ""

    if proc.returncode != 0:
        msg = "\n".join(
            [
                f"[python_exec error] returncode={proc.returncode}",
                "STDOUT:",
                out_str,
                "STDERR:",
                err_str,
            ]
        )
        if cb.truncate_output is not None:
            return cb.truncate_output("python_exec", msg, 400_000)
        return msg

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += "\n[stderr]\n" + err_str

    if cb.truncate_output is not None:
        return cb.truncate_output("python_exec", out_str, 400_000)
    return out_str


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    if "code" not in args:
        return _("[python_exec error] Provide 'code'.")
    return _run_python_code(args, cb)
