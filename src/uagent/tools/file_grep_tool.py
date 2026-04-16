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

# 除外するディレクトリのデフォルトリスト
DEFAULT_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".uag", "dist", "build"}

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
        "description": _("tool.description", default="Search for a pattern in files and return matching lines with line numbers (like grep -n). Supports multiple paths and context lines."),
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
                    "default": "*",
                },
                "recursive": {
                    "type": "boolean",
                    "description": _("param.recursive.description", default="Whether to search subdirectories recursively."),
                    "default": False,
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": _("param.ignore_case.description", default="Whether to ignore case (default: true)."),
                    "default": True,
                },
                "max_results": {
                    "type": "integer",
                    "description": _("param.max_results.description", default="Maximum number of match lines to return (default: 100)."),
                    "default": 100,
                },
                "context_lines": {
                    "type": "integer",
                    "description": _("param.context_lines.description", default="Number of lines of leading and trailing context to each match."),
                    "default": 0,
                },
                "filenames_only": {
                    "type": "boolean",
                    "description": _("param.filenames_only.description", default="If true, only return the list of filenames with matches."),
                    "default": False,
                },
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    },
}

def _is_binary(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except:
        return False

def _resolve_files(raw_path: str | list[str], name_pattern: str, recursive: bool) -> List[str]:
    items = [raw_path] if isinstance(raw_path, str) else raw_path
    all_files = []
    seen = set()

    for item in items:
        try:
            safe_item = ensure_within_workdir(item)
        except Exception:
            continue

        if os.path.isfile(safe_item):
            if safe_item not in seen:
                seen.add(safe_item); all_files.append(safe_item)
        else:
            if recursive:
                # 手動でノイズディレクトリを除外しながら走査
                for root, dirs, files_in_dir in os.walk(safe_item):
                    # インプレースで dirs を修正して特定のディレクトリへの侵入を防ぐ
                    dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_DIRS]

                    # glob.fnmatch でフィルタリング
                    import fnmatch
                    for f in sorted(fnmatch.filter(files_in_dir, name_pattern)):
                        full_p = os.path.abspath(os.path.join(root, f))
                        if full_p not in seen:
                            seen.add(full_p); all_files.append(full_p)
            else:
                search_glob = os.path.join(safe_item, name_pattern)
                matches = glob.glob(search_glob, recursive=False)
                for m in sorted(matches):
                    if os.path.isfile(m):
                        abs_m = os.path.abspath(m)
                        if abs_m not in seen:
                            seen.add(abs_m); all_files.append(abs_m)
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
        context_lines = get_int(args, "context_lines", 0)
        filenames_only = get_bool(args, "filenames_only", False)

        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return _json_err(_("err.invalid_regex", default="Invalid regex pattern."), detail=str(e))

        files = _resolve_files(raw_path, name_pattern, recursive)
        if not files:
            return _json_ok(matches=[], count=0, message=_("err.no_files_found", default="No files found matching the criteria."))

        results_list = []
        matched_filenames = []
        total_match_count = 0
        limit_reached = False

        for file_path in files:
            if total_match_count >= max_results:
                limit_reached = True; break

            if _is_binary(file_path):
                continue

            try:
                display_path = os.path.relpath(file_path, os.getcwd())
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                file_has_match = False
                file_matches = []

                for i, line in enumerate(lines):
                    if regex.search(line):
                        file_has_match = True
                        if filenames_only:
                            break

                        # Context
                        start_idx = max(0, i - context_lines)
                        end_idx = min(len(lines), i + context_lines + 1)

                        context_block = []
                        for j in range(start_idx, end_idx):
                            prefix = "> " if j == i else "  "
                            context_block.append(f"{display_path}:{j+1}{prefix}{lines[j].rstrip('\\r\\n')}")

                        file_matches.append("\n".join(context_block))
                        total_match_count += 1
                        if total_match_count >= max_results:
                            limit_reached = True; break

                if file_has_match:
                    matched_filenames.append(display_path)
                    results_list.extend(file_matches)

            except Exception:
                continue

        if filenames_only:
            return _json_ok(matches=matched_filenames, count=len(matched_filenames), filenames_only=True)

        return _json_ok(matches=results_list, limit_reached=limit_reached, count=len(results_list))

    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception occurred during grep operations."),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, "tool:file_grep")
