from __future__ import annotations

import io
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from typing import Any

from ..runtime.tool_execution_result import ToolExecutionText
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:python_exec"
_CODE_PREVIEW_MAX_CHARS = 120
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?P<name>(?:[A-Za-z_]\w*)?"
    r"(?:secret|password|passwd|pwd|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|credential|authorization|auth|cookie)\w*)\s*="
)


TOOL_SPEC: dict[str, Any] = {
    "computer_use_conflict": True,
    "type": "function",
    "tool_genre": "exec",
    "function": {
        "name": "python_exec",
        "description": _(
            "tool.description",
            default=(
                "Execute Python code in a controlled way. Use this tool for calculations, data processing, or running short scripts. Search for other suitable tools via `tool_catalog` before using this tool."
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


def _safe_code_preview(code: Any) -> str:
    """Return a short first-line preview with comments and literal values masked."""
    source = code if isinstance(code, str) else str(code or "")
    line = next(
        (
            candidate.strip()
            for candidate in source.splitlines()
            if candidate.strip() and not candidate.lstrip().startswith("#")
        ),
        "",
    )
    if not line:
        return "<empty script>"

    sensitive_assignment = _SENSITIVE_ASSIGNMENT_RE.search(line)
    if sensitive_assignment:
        preview = f"{sensitive_assignment.group('name')} = <redacted>"
    else:
        safe_tokens = []
        try:
            for item in tokenize.generate_tokens(io.StringIO(line).readline):
                if item.type == tokenize.COMMENT:
                    break
                if item.type == tokenize.STRING:
                    item = item._replace(string="'<string>'")
                elif item.type == tokenize.NUMBER:
                    item = item._replace(string="0")
                safe_tokens.append(item)
            preview = tokenize.untokenize(safe_tokens).strip()
        except (IndentationError, tokenize.TokenError):
            return "<preview unavailable>"

    if len(preview) > _CODE_PREVIEW_MAX_CHARS:
        preview = preview[: _CODE_PREVIEW_MAX_CHARS - 3] + "..."
    return preview or "<preview unavailable>"


def describe(args: dict[str, Any]) -> str:
    """Show a masked preview of the submitted Python source."""
    return str(
        _(
            "describe.python",
            default="Run Python code (preview): %(code)s",
            code=_safe_code_preview(args.get("code", "")),
        )
    )


TOOL_DESCRIBER = describe
