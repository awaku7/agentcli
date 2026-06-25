from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any
import glob
import json
import os
import py_compile
from pathlib import Path

BUSY_LABEL = True
STATUS_LABEL = "tool:python_compile"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "devel",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "python_compile",
        "description": _(
            "tool.description",
            default="Validate Python files with py_compile. Use this tool for syntax checking Python files, directories, or glob patterns.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "python_compile",
                "python compile",
            ],
        ),
        "x_search_terms_en": [
            "python_compile",
            "python compile",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="A Python file, directory, or glob pattern to validate with py_compile. Directories are scanned recursively for *.",
                    ),
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.paths.description",
                        default="Multiple Python files, directories, or glob patterns to validate with py_compile. Directories are scanned recursively for .py files.",
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

    for raw_target in raw_targets:
        if not raw_target:
            continue

        candidates: list[str]
        if any(ch in raw_target for ch in "*?[]"):
            # Glob pattern
            candidates = glob.glob(raw_target, recursive=True)
            if not candidates:
                missing.append(raw_target)
                continue
        elif os.path.isdir(raw_target):
            # Directory: scan recursively for .py files
            p = Path(raw_target)
            candidates = [str(f) for f in p.rglob("*.py")]
            if not candidates:
                missing.append(raw_target)
                continue
        else:
            # Single file or exact path
            if os.path.isfile(raw_target):
                candidates = [raw_target]
            else:
                missing.append(raw_target)
                continue

        for c in candidates:
            if c.endswith(".py") and c not in resolved:
                resolved.append(c)

    return resolved, missing


def _run_compile(resolved: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fpath in resolved:
        try:
            py_compile.compile(fpath, doraise=True)
            results.append({"path": fpath, "ok": True})
        except py_compile.PyCompileError as e:
            results.append({"path": fpath, "ok": False, "error": str(e)})
        except Exception as e:
            results.append(
                {"path": fpath, "ok": False, "error": f"{type(e).__name__}: {e}"}
            )
    return results


def run_tool(args: dict[str, Any]) -> str:
    raw_targets: list[str] = _as_str_list(args.get("path") or args.get("paths") or ".")

    resolved, missing = _resolve_py_compile_targets(raw_targets)

    if not resolved:
        return json.dumps(
            {
                "ok": False,
                "summary": "No Python files found to compile",
                "targets_requested": raw_targets,
                "missing": missing,
                "results": [],
            },
            ensure_ascii=False,
        )

    results = _run_compile(resolved)

    total = len(results)
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = total - ok_count

    return json.dumps(
        {
            "ok": fail_count == 0,
            "summary": f"{ok_count} passed, {fail_count} failed out of {total} files",
            "total": total,
            "passed": ok_count,
            "failed": fail_count,
            "targets_requested": raw_targets,
            "missing": missing,
            "results": results,
        },
        ensure_ascii=False,
    )
