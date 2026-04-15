from __future__ import annotations

# src/uagent/tools/file_grep_tool.py

import json
import os
import re
import glob
from typing import Any, Dict, List

from .arg_util import get_bool, get_int, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)


def _json_ok(**obj: Any) -> str:
    out: Dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: Dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "file_grep",
        "description": _("tool.description", default="Search for a pattern in files and return matching lines with line numbers (like grep -n)."),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": _("param.pattern.description", default="Regex pattern to search for."),
                },
                "path": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": _("param.path.description", default="Root directory or specific file path (default: '.')."),
                },
                "name_pattern": {
                    "type": "string",
                    "description": _("param.name_pattern.description", default="Glob pattern for filenames (e.g., '*.py')."),
                },
                "recursive": {
                    "type": "boolean",
                    "description": _("param.recursive.description", default="Whether to search subdirectories recursively."),
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": _("param.ignore_case.description", default="Whether to ignore case (default: true)."),
                },
                "max_results": {
                    "type": "integer",
                    "description": _("param.max_results.description", default="Maximum number of match lines to return (default: 100)."),
                },
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    },
}


def _resolve_files(raw_path: str | list[str], name_pattern: str, recursive: bool) -> List[str]:
    items = [raw_path] if isinstance(raw_path, str) else raw_path
    all_files = []
    seen = set()

    for item in items:
        try:
            # プレースホルダや絶対パスなどのリスクを避けるため workdir 内に限定
            safe_item = ensure_within_workdir(item)
        except Exception:
            continue

        if os.path.isfile(safe_item):
            if safe_item not in seen:
                seen.add(safe_item)
                all_files.append(safe_item)
        else:
            # ディレクトリまたは glob として扱う
            if recursive:
                search_glob = os.path.join(safe_item, "**", name_pattern)
            else:
                search_glob = os.path.join(safe_item, name_pattern)
            
            matches = glob.glob(search_glob, recursive=recursive)
            for m in sorted(matches):
                if os.path.isfile(m):
                    abs_m = os.path.abspath(m)
                    if abs_m not in seen:
                        seen.add(abs_m)
                        all_files.append(abs_m)
    return all_files


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, "tool:file_grep")
    try:
        pattern = get_str(args, "pattern", "")
        if not pattern:
            return _json_err(_("err.missing_pattern", default="Missing 'pattern'."))

        raw_path = args.get("path", ".")
        name_pattern = get_str(args, "name_pattern", "*")
        recursive = get_bool(args, "recursive", False)
        ignore_case = get_bool(args, "ignore_case", True)
        max_results = get_int(args, "max_results", 100)

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return _json_err(_("err.invalid_regex", default="Invalid regex pattern."), detail=str(e))

        files = _resolve_files(raw_path, name_pattern, recursive)
        
        if not files:
            return _json_ok(matches=[], count=0, message=_("err.no_files_found", default="No files found matching the criteria."))

        matches = []
        count = 0
        limit_reached = False

        for file_path in files:
            if count >= max_results:
                limit_reached = True
                break
            try:
                # 表示用パスはカレントディレクトリからの相対
                display_path = os.path.relpath(file_path, os.getcwd())
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if regex.search(line):
                            matches.append(f"{display_path}:{line_no}:{line.strip()}")
                            count += 1
                            if count >= max_results:
                                limit_reached = True
                                break
            except Exception:
                continue

        return _json_ok(matches=matches, limit_reached=limit_reached, count=len(matches))

    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception occurred during grep operations."),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, "tool:file_grep")
