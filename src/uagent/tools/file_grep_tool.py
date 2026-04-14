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
        "system_prompt": _("tool.system_prompt", default="Search files for a pattern. Return JSON with 'matches' list."),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": _("param.pattern.description", default="Regex pattern to search for."),
                },
                "path": {
                    "type": "string",
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


def run_tool(args: Dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, "tool:file_grep")
    try:
        pattern = get_str(args, "pattern", "")
        if not pattern:
            return _json_err(_("err.missing_pattern", default="Missing 'pattern'."))

        path = get_str(args, "path", ".")
        name_pattern = get_str(args, "name_pattern", "*")
        recursive = get_bool(args, "recursive", False)
        ignore_case = get_bool(args, "ignore_case", True)
        max_results = get_int(args, "max_results", 100)

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return _json_err(_("err.invalid_regex", default="Invalid regex pattern."), detail=str(e))

        search_root = os.path.abspath(path)
        if os.path.isfile(search_root):
            files = [search_root]
        else:
            if recursive:
                search_glob = os.path.join(search_root, "**", name_pattern)
            else:
                search_glob = os.path.join(search_root, name_pattern)
            files = [f for f in glob.glob(search_glob, recursive=recursive) if os.path.isfile(f)]

        matches = []
        count = 0
        limit_reached = False

        for file_path in files:
            if count >= max_results:
                limit_reached = True
                break
            try:
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
