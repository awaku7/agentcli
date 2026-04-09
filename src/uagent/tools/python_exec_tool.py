from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict
import glob
import json
import os
import py_compile
import subprocess
import tempfile
from pathlib import Path

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
                "Execute Python code or validate Python files with py_compile. Use this tool for calculations, "
                "data processing, running short scripts, or syntax checking files—especially when accuracy matters. "
                "Use 'code' to run Python, and use 'path'/'paths' only to validate files with py_compile. "
                "Do not pass empty strings for 'path' or 'paths', and do not mix 'code' with 'path'/'paths' in one request. "
                "Prefer this over cmd_exec/cmd_exec_json for Python work."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Execute Python code in a controlled way.\n"
                "- If you need Python standard library features or reliable numeric computation, use this tool.\n"
                "- If file paths or glob patterns are supplied, run py_compile on those targets and return the result.\n"
                "- When you are about to run code, briefly state what will be executed.\n"
                "- Do not use cmd_exec to run Python unless explicitly necessary."
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
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default=(
                            "A Python file, directory, or glob pattern to validate with py_compile. "
                            "Directories are scanned recursively for *.py files."
                        ),
                    ),
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.paths.description",
                        default=(
                            "Multiple Python files, directories, or glob patterns to validate with py_compile. "
                            "Directories are scanned recursively for *.py files."
                        ),
                    ),
                },
            },
        },
    },
}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, os.PathLike)):
        return [os.fspath(value)]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, os.PathLike):
                out.append(os.fspath(item))
            else:
                out.append(str(item))
        return out
    return [str(value)]


def _resolve_py_compile_targets(raw_targets: list[str]) -> tuple[list[str], list[str]]:
    resolved: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for raw_target in raw_targets:
        if not raw_target:
            continue

        candidates: list[str]
        if any(ch in raw_target for ch in "*?[]"):
            candidates = glob.glob(raw_target, recursive=True)
        else:
            target_path = Path(raw_target)
            if target_path.is_dir():
                candidates = [str(p) for p in target_path.rglob("*.py")]
            elif target_path.exists():
                candidates = [str(target_path)]
            else:
                missing.append(raw_target)
                continue

        for candidate in candidates:
            candidate_path = Path(candidate)
            if candidate_path.is_dir():
                continue
            normalized = str(candidate_path)
            if normalized not in seen:
                seen.add(normalized)
                resolved.append(normalized)

    return resolved, missing


def _run_py_compile(args: Dict[str, Any]) -> str:
    raw_targets = _as_str_list(args.get("paths"))
    raw_targets.extend(_as_str_list(args.get("path")))
    raw_targets = [t for t in raw_targets if str(t).strip()]

    resolved_targets, missing = _resolve_py_compile_targets(raw_targets)
    compiled: list[str] = []
    failed: list[dict[str, str]] = []

    for file_path in resolved_targets:
        try:
            py_compile.compile(file_path, doraise=True)
        except py_compile.PyCompileError as e:
            failed.append({"path": file_path, "error": str(e)})
        except Exception as e:
            failed.append({"path": file_path, "error": f"{type(e).__name__}: {e}"})
        else:
            compiled.append(file_path)

    result = {
        "ok": not missing and not failed and bool(resolved_targets),
        "mode": "py_compile",
        "targets": raw_targets,
        "resolved": resolved_targets,
        "compiled": compiled,
        "failed": failed,
        "missing": missing,
        "count": len(compiled),
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


def _run_python_code(args: Dict[str, Any], cb: Any) -> str:
    code = args.get("code", "")
    if not isinstance(code, str):
        code = str(code)

    # Write to a temp file and execute (python -c can be unreliable in some environments)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(code)
            tmp_path = tf.name

        proc = subprocess.run(
            ["python", tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=(cb.cmd_encoding or "utf-8"),
            errors="replace",
            timeout=cb.python_exec_timeout_ms / 1000.0,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"[python_exec timeout] Did not finish within {cb.python_exec_timeout_ms / 1000:.0f} seconds"
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
        msg = (
            f"[python_exec error] returncode={proc.returncode}\n"
            f"STDOUT:\n{out_str}\n"
            f"STDERR:\n{err_str}"
        )
        if cb.truncate_output is not None:
            return cb.truncate_output("python_exec", msg, 400_000)
        return msg

    if not out_str.strip():
        out_str = "(no output)"
    if err_str.strip():
        out_str += f"\n[stderr]\n{err_str}"

    if cb.truncate_output is not None:
        return cb.truncate_output("python_exec", out_str, 400_000)
    return out_str


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()

    raw_targets = [
        t
        for t in _as_str_list(args.get("paths")) + _as_str_list(args.get("path"))
        if str(t).strip()
    ]
    if raw_targets:
        args = dict(args)
        args["path"] = ""
        args["paths"] = raw_targets
        return _run_py_compile(args)

    if "code" not in args:
        return _("[python_exec error] Provide either 'code' or 'path'/'paths'.")

    return _run_python_code(args, cb)
