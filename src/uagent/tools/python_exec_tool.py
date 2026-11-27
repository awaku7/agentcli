from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Any

from ..runtime.tool_execution_result import ToolExecutionText
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:python_exec"


TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "type": "function",
    "tool_level": 1,
    "function": {
        "name": "python_exec",
        "description": _(
            "tool.description",
            default=(
                "Run short Python code as a temporary script using the active interpreter "
                "(not an interactive REPL). Standard input is closed, a configured "
                "timeout applies, and stdout/stderr are returned. The script inherits "
                "the agent process's working directory and environment. Prefer "
                "dedicated tools for supported operations; search `tool_catalog` for "
                "other suitable tools before using this tool."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "python",
                "run python",
                "execute script",
                "Execute Python",
                "ejecutar python",
                "exécuter python",
                "파이썬 실행",
                "запустить python",
            ],
        ),
        "x_search_terms_en": [
            "python",
            "run python",
            "execute script",
            "Execute Python",
            "ejecutar python",
            "exécuter python",
            "파이썬 실행",
            "запустить python",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": _(
                        "param.code.description",
                        default=(
                            "Python code to run, such as a short calculation or data-processing script."
                        ),
                    ),
                },
            },
            "required": ["code"],
        },
    },
}


def _run_python_code(args: dict[str, Any], cb: Any) -> str:
    code = args.get("code", "")
    if not isinstance(code, str):
        code = str(code)

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(code)
            tmp_path = tf.name

        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, tmp_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=(cb.cmd_encoding or "utf-8"),
            errors="replace",
            timeout=cb.python_exec_timeout_ms / 1000.0,
            shell=False,
            env=child_env,
        )
    except subprocess.TimeoutExpired:
        return ToolExecutionText(
            f"[python_exec timeout] Did not finish within {cb.python_exec_timeout_ms / 1000:.0f} seconds",
            status="timeout",
        )
    except Exception as e:
        return ToolExecutionText(
            f"[python_exec error] {type(e).__name__}: {e}", status="failed"
        )
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
            return ToolExecutionText(
                cb.truncate_output("python_exec", msg, 400_000), status="failed"
            )
        return ToolExecutionText(msg, status="failed")

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += "\n[stderr]\n" + err_str

    if cb.truncate_output is not None:
        return ToolExecutionText(cb.truncate_output("python_exec", out_str, 400_000))
    return ToolExecutionText(out_str)


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()
    if "code" not in args:
        return _("[python_exec error] Provide 'code'.")
    return _run_python_code(args, cb)


def describe(_args: dict[str, Any]) -> str:
    """Describe the action without echoing any submitted source code."""
    return str(
        _(
            "describe.python",
            default=(
                "Run the supplied Python code as a temporary script using the active "
                "interpreter. Standard input is closed, a configured timeout applies, "
                "and standard output/error are returned. The script inherits the "
                "agent process's working directory and environment."
            ),
        )
    )


TOOL_DESCRIBER = describe
