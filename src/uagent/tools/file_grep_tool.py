from __future__ import annotations

# src/uagent/tools/file_grep_tool.py

import fnmatch
import json
import os
import re
from typing import Any, Sequence

from .arg_util import get_bool, get_int, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:file_grep"

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    ".uag",
    "dist",
    "build",
}
DEFAULT_EXCLUDE_GLOBS = {
    "*.pyc",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.exe",
    "*.bin",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
}

_TEXT_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc_jp")


def _json_ok(**obj: Any) -> str:
    out: dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "basic",
    "x_parallel_safe": True,
    "function": {
        "name": "file_grep",
        "description": _(
            "tool.description",
            default="Search for a pattern in files and return matching lines with line numbers (like grep -n). Pattern is required.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "grep",
                "search lines",
                "find in file",
                "ファイル内検索",
                "buscar en archivos",
                "rechercher dans les fichiers",
                "파일 검색",
                "поиск в файлах",
            ],
        ),
        "x_search_terms_en": [
            "grep",
            "search lines",
            "find in file",
            "ファイル内検索",
            "buscar en archivos",
            "rechercher dans les fichiers",
            "파일 검색",
            "поиск в файлах",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": _(
                        "param.pattern.description",
                        default="Regex pattern to search for.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Root directory or file path to search.",
                    ),
                },
                "root_path": {
                    "type": "string",
                    "description": _(
                        "param.root_path.description",
                        default="Alias (compat).",
                    ),
                },
                "glob": {
                    "type": "string",
                    "description": _(
                        "param.glob.description",
                        default=(
                            "Filename glob pattern (e.g., '*.py', 'test_*'). "
                            "If omitted, all files are considered."
                        ),
                    ),
                    "default": "*",
                },
                "recur": {
                    "type": "boolean",
                    "description": _(
                        "param.recur.description",
                        default="Whether to search subdirectories recursively.",
                    ),
                    "default": False,
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": _(
                        "param.ignore_case.description",
                        default="Whether to ignore case (default: true).",
                    ),
                    "default": True,
                },
                "literal": {
                    "type": "boolean",
                    "description": _(
                        "param.literal.description",
                        default="If true, treat pattern as a literal string instead of regex.",
                    ),
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of matches to return per page (default: 100).",
                    ),
                    "default": 100,
                },
                "page": {
                    "type": "integer",
                    "description": _(
                        "param.page.description",
                        default="Page number to retrieve (default: 1).",
                    ),
                    "default": 1,
                },
                "maxhits": {
                    "type": "integer",
                    "description": _(
                        "param.maxhits.description",
                        default="Maximum number of matches to return per file (default: 100).",
                    ),
                    "default": 100,
                },
                "context_lines": {
                    "type": "integer",
                    "description": _(
                        "param.context_lines.description",
                        default="Number of lines of leading and trailing context for each match.",
                    ),
                    "default": 0,
                },
                "filenames_only": {
                    "type": "boolean",
                    "description": _(
                        "param.filenames_only.description",
                        default="If enabled, return only the list of filenames with matches.",
                    ),
                    "default": False,
                },
                "exclude_dirs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.exclude_dirs.description",
                        default="Directory names to exclude from recursive walking.",
                    ),
                    "default": [],
                },
                "exclude_globs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.exclude_globs.description",
                        default="Filename glob patterns to exclude.",
                    ),
                    "default": [],
                },
                "binary_skip": {
                    "type": "boolean",
                    "description": _(
                        "param.binary_skip.description",
                        default="Skip files that look like binary files.",
                    ),
                    "default": True,
                },
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    },
}


def _is_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
        if not head:
            return False
        if b"\x00" in head:
            return True
        bad = 0
        for b in head:
            if b in (9, 10, 13):
                continue
            if 0 <= b < 32:
                bad += 1
        return (bad / len(head)) > 0.10
    except Exception:
        return False


def _normalize_items(raw_path: Any) -> list[str]:
    if raw_path is None:
        return ["."]
    if isinstance(raw_path, str):
        return [raw_path]
    if isinstance(raw_path, Sequence):
        return [str(x) for x in raw_path if str(x)]
    return [str(raw_path)]


def _resolve_files(
    raw_path: Any,
    name_pattern: str,
    recursive: bool,
    exclude_dirs: set[str],
    exclude_globs: list[str],
) -> list[str]:
    items = _normalize_items(raw_path)
    all_files: list[str] = []
    seen: set[str] = set()

    for item in items:
        try:
            safe_item = ensure_within_workdir(item)
        except Exception:
            continue

        if os.path.isfile(safe_item):
            abs_item = os.path.abspath(safe_item)
            if abs_item not in seen:
                seen.add(abs_item)
                all_files.append(abs_item)
            continue

        if not os.path.isdir(safe_item):
            continue

        if recursive:
            for root, dirs, files_in_dir in os.walk(safe_item):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for fname in sorted(fnmatch.filter(files_in_dir, name_pattern)):
                    if any(fnmatch.fnmatch(fname, g) for g in exclude_globs):
                        continue
                    full_p = os.path.abspath(os.path.join(root, fname))
                    if full_p not in seen:
                        seen.add(full_p)
                        all_files.append(full_p)
        else:
            try:
                with os.scandir(safe_item) as it:
                    entries = sorted(
                        (entry for entry in it if entry.is_file()), key=lambda e: e.name
                    )
            except FileNotFoundError:
                continue
            for entry in entries:
                base = entry.name
                if not fnmatch.fnmatch(base, name_pattern):
                    continue
                if any(fnmatch.fnmatch(base, g) for g in exclude_globs):
                    continue
                abs_m = os.path.abspath(entry.path)
                if abs_m not in seen:
                    seen.add(abs_m)
                    all_files.append(abs_m)

    return all_files


def _compile_pattern(pattern: str, literal: bool, ignore_case: bool) -> re.Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    expr = re.escape(pattern) if literal else pattern
    return re.compile(expr, flags)


def _ordered_encodings(preferred: str | None = None) -> list[str]:
    order: list[str] = []
    if preferred:
        order.append(preferred)
    for enc in _TEXT_ENCODING_CANDIDATES:
        if enc not in order:
            order.append(enc)
    return order


def _detect_text_encoding(head: bytes) -> str:
    if not head:
        return "utf-8"
    if head.startswith(b"\xef\xbb\xbf"):

        return "utf-8-sig"
    for enc in _TEXT_ENCODING_CANDIDATES:
        try:
            head.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue
        return enc
    return "utf-8"


def _decode_text_bytes(data: bytes) -> tuple[str, str]:
    preferred = _detect_text_encoding(data[:8192])
    for enc in _ordered_encodings(preferred):
        try:
            text = data.decode(enc, errors="strict")
            return text.replace("\r\n", "\n").replace("\r", "\n"), enc
        except UnicodeDecodeError:
            continue
    return (
        data.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n"),
        "utf-8",
    )


def _read_lines(path: str) -> list[str]:
    with open(path, "rb") as f:
        data = f.read()
    text, _encoding = _decode_text_bytes(data)
    return text.splitlines(keepends=True)


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, STATUS_LABEL)
    try:
        pattern = get_str(args, "pattern", "")
        if not pattern:
            return _json_err(
                _("err.pattern_required", default="Error: pattern is required.")
            )

        raw_path = args.get("path")
        if raw_path in (None, ""):
            raw_path = args.get("root_path", ".")

        name_pattern = get_str(args, "glob", "*")
        recursive = get_bool(args, "recur", False)
        ignore_case = get_bool(args, "ignore_case", True)
        literal = get_bool(args, "literal", False)
        max_results = max(0, get_int(args, "limit", 100))
        page = max(1, get_int(args, "page", 1))
        max_hits_per_file = max(0, get_int(args, "maxhits", 100))
        context_lines = max(0, get_int(args, "context_lines", 0))
        filenames_only = get_bool(args, "filenames_only", False)
        binary_skip = get_bool(args, "binary_skip", True)

        exclude_dirs_raw = args.get("exclude_dirs", []) or []
        exclude_globs_raw = args.get("exclude_globs", []) or []
        if isinstance(exclude_dirs_raw, str):
            exclude_dirs = {exclude_dirs_raw}
        else:
            exclude_dirs = {str(x) for x in exclude_dirs_raw if str(x)}
        if isinstance(exclude_globs_raw, str):
            exclude_globs = [exclude_globs_raw]
        else:
            exclude_globs = [str(x) for x in exclude_globs_raw if str(x)]

        exclude_dirs = set(DEFAULT_EXCLUDE_DIRS).union(exclude_dirs)
        exclude_globs = list(DEFAULT_EXCLUDE_GLOBS) + exclude_globs

        try:
            regex = _compile_pattern(pattern, literal=literal, ignore_case=ignore_case)
        except re.error as e:
            return _json_err(
                _(
                    "err.regex_compile",
                    default="[file_grep error] Failed to compile regex: {error}",
                ).format(error=str(e))
            )

        files = _resolve_files(
            raw_path, name_pattern, recursive, exclude_dirs, exclude_globs
        )
        matched_files: set[str] = set()
        filenames: list[str] = []
        matches: list[dict[str, Any]] = []
        scanned_files = 0
        skipped_binary = 0

        for path in files:
            scanned_files += 1

            if binary_skip and _is_binary(path):
                skipped_binary += 1
                continue

            try:
                lines = _read_lines(path)
            except Exception:
                continue

            file_hit_count = 0
            file_matched = False
            for idx, line in enumerate(lines):
                if not regex.search(line):
                    continue

                file_matched = True
                file_hit_count += 1

                if filenames_only:
                    break

                start_idx = max(0, idx - context_lines)
                end_idx = min(len(lines), idx + context_lines + 1)
                before = [ln.rstrip("\r\n") for ln in lines[start_idx:idx]]
                after = [ln.rstrip("\r\n") for ln in lines[idx + 1 : end_idx]]
                text = line.rstrip("\r\n")
                matches.append(
                    {
                        "file": path,
                        "line": idx + 1,
                        "text": text,
                        "context_before": before,
                        "context_after": after,
                    }
                )
                if max_hits_per_file and file_hit_count >= max_hits_per_file:
                    break

            if file_matched:
                matched_files.add(path)
                if filenames_only:
                    filenames.append(path)

        from .pagination_util import paginate_results

        if filenames_only:
            page_results, page, total_pages, total_results = paginate_results(
                filenames, page, max_results
            )
            return _json_ok(
                filenames=page_results,
                count=len(page_results),
                total_results=total_results,
                page=page,
                total_pages=total_pages,
                scanned_files=scanned_files,
                matched_files=len(matched_files),
                skipped_binary=skipped_binary,
                pattern=pattern,
                literal=literal,
                ignore_case=ignore_case,
            )

        page_results, page, total_pages, total_results = paginate_results(
            matches, page, max_results
        )
        return _json_ok(
            matches=page_results,
            count=len(page_results),
            total_results=total_results,
            page=page,
            total_pages=total_pages,
            scanned_files=scanned_files,
            matched_files=len(matched_files),
            skipped_binary=skipped_binary,
            pattern=pattern,
            literal=literal,
            ignore_case=ignore_case,
            context_lines=context_lines,
        )
    except Exception as e:
        return _json_err(str(e))
    finally:
        if cb.set_status:
            cb.set_status(False, STATUS_LABEL)
