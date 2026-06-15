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
    "function": {
        "name": "python_compile",
        "description": _(
            "tool.description",
            default="Validate Python files with py_compile. Use this tool for syntax checking Python files, directories, or glob patterns.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Validate Python files with py_compile. If file paths or glob patterns are supplied, run py_compile on those targets and return the result."
            ),
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
                        default="Multiple Python files, directories, or glob patterns to validate with py_compile. Directories are scanned recursively...",
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


def run_tool(args: dict[str, Any]) -> str:
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
