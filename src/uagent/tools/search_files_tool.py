from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from typing import Any, Optional

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# Mark as busy while running
BUSY_LABEL = True
STATUS_LABEL = "tool:search_files"


def _json_err(message: str, **extra: Any) -> str:
    obj: dict[str, Any] = {"ok": False, "error": message}
    obj.update(extra)
    return json.dumps(obj, ensure_ascii=False)


TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "function": {
        "name": "search_files",
        "description": _(
            "tool.description",
            default="Search files under a directory by filename glob and optionally by content regex.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Search for files under a directory. You can filter by filename pattern (glob) and optionally "
                "grep file contents using a regular expression. "
                "Use path or root_path to choose the search root.\n\n"
                "Notes:\n"
                "- content_pattern is treated as a Python regular expression.\n"
                "- If content_pattern is empty, only filename matching is performed.\n"
                "- For performance, content searching may use a simple binary check internally."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "search files",
                "glob",
                "regex search",
                "ファイル検索",
                "buscar archivos",
                "rechercher des fichiers",
                "파일 찾기",
                "поиск файлов",
            ],
        ),
        "x_search_terms_en": [
            "search files",
            "glob",
            "regex search",
            "ファイル検索",
            "buscar archivos",
            "rechercher des fichiers",
            "파일 찾기",
            "поиск файлов",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Root directory to start searching from (default: current directory). Alias of root_path.",
                    ),
                },
                "root_path": {
                    "type": "string",
                    "description": _(
                        "param.root_path.description",
                        default="Alias of path for backward compatibility.",
                    ),
                },
                "name_pattern": {
                    "type": "string",
                    "description": _(
                        "param.name_pattern.description",
                        default="Filename glob pattern (e.g., '*.py', 'test_*'). If omitted, all files are considered.",
                    ),
                },
                "content_pattern": {
                    "type": "string",
                    "description": _(
                        "param.content_pattern.description",
                        default="Regular expression to search within files. If omitted, only filename matching is performed.",
                    ),
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": _(
                        "param.case_sensitive.description",
                        default="Whether the content search is case-sensitive (default: false).",
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": _(
                        "param.max_results.description",
                        default="Maximum number of matched files to return per page (default: 50).",
                    ),
                },
                "page": {
                    "type": "integer",
                    "description": _(
                        "param.page.description",
                        default="Page number to retrieve (default: 1).",
                    ),
                    "default": 1,
                },
                "fast_read_threshold_bytes": {
                    "type": "integer",
                    "description": _(
                        "param.fast_read_threshold_bytes.description",
                        default=(
                            "Files smaller than this threshold are fully read() for faster searching (default: 8000000 ≈ 8MB). "
                            "Larger files are scanned line-by-line."
                        ),
                    ),
                    "default": 8000000,
                },
            },
            "required": [],
        },
    },
}


# Directories to exclude from walking
IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    ".vscode",
    "coverage",
}

# File extensions to exclude only for content-search safety/performance.
# Filename-only searches should still be able to list image files.
IGNORE_EXTS = {
    ".pyc",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
}


_TEXT_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc_jp")


def _looks_binary(head: bytes) -> bool:
    """Heuristically determine whether a file is likely binary."""

    if not head:
        return False

    # NUL almost certainly indicates binary
    if b"\x00" in head:
        return True

    # Allow a small set of common control characters: \t, \n, \r
    bad = 0
    for b in head:
        if b in (9, 10, 13):
            continue
        if 0 <= b < 32:
            bad += 1

    # If 10%+ of the sample are control chars, treat as binary-ish.
    return (bad / len(head)) > 0.10


_ANY_NL_RE_FRAGMENT = r"(?:\r\n|\n|\r)"
_NL_MARKER = "__UAGENT_NL__"


def _normalize_newline_tokens_in_pattern(content_pattern: str) -> str:
    """Normalize user-supplied content_pattern so that newline tokens match any newline.

    Supports BOTH:
    - Pasted real newlines in the pattern (actual '\n' or '\r')
    - JSON/CLI style escaped sequences (literal backslash tokens): "\\n", "\\r", "\\r\\n"

    Implementation:
    - First replace literal backslash tokens (\\r\\n / \\r / \\n) with a plain marker.
    - Then replace actual newline characters (\r\n / \r / \n) with the marker.
    - Finally expand the marker once into a stable regex fragment.
    """

    cp = content_pattern

    # 1) Literal backslash tokens (NOTE: patterns must be r"\\n" etc.)
    cp = cp.replace(r"\\r\\n", _NL_MARKER)
    cp = cp.replace(r"\\r", _NL_MARKER)
    cp = cp.replace(r"\\n", _NL_MARKER)

    # 2) Actual newlines (pasted text)
    cp = cp.replace("\r\n", _NL_MARKER)
    cp = cp.replace("\r", _NL_MARKER)
    cp = cp.replace("\n", _NL_MARKER)

    # 3) Expand marker once
    if _NL_MARKER in cp:
        cp = cp.replace(_NL_MARKER, _ANY_NL_RE_FRAGMENT)

    return cp


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


def _grep_text_full_read_bytes(
    data: bytes,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> list[str]:
    """For small/medium files: decode once and grep quickly."""

    text, _encoding = _decode_text_bytes(data)

    m0 = regex.search(text)
    if not m0:
        return []

    matched_lines: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if regex.search(line):
            matched_lines.append(
                _("match.line", default="L{line}: {text}").format(
                    line=i, text=line.strip()[:200]
                )
            )
            if len(matched_lines) >= max_hits_per_file:
                matched_lines.append(
                    _("match.more", default="... (more matches in file)")
                )
                break

    # If the match spans lines, line-by-line hits will be empty.
    if not matched_lines:
        s = max(0, m0.start() - 80)
        e = min(len(text), m0.end() + 80)
        excerpt = text[s:e].replace("\n", "\\n").replace("\r", "\\r")
        matched_lines.append(
            _("match.excerpt", default="MATCH: {text}").format(text=excerpt[:200])
        )

    return matched_lines


def _read_text_auto(full_path: str) -> tuple[str, str]:
    with open(full_path, "rb") as f:
        data = f.read()
    return _decode_text_bytes(data)


def _grep_text_full_read(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> list[str]:
    """Backward-compatible wrapper for path-based callers."""

    text, _encoding = _read_text_auto(full_path)
    m0 = regex.search(text)
    if not m0:
        return []

    matched_lines: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if regex.search(line):
            matched_lines.append(
                _("match.line", default="L{line}: {text}").format(
                    line=i, text=line.strip()[:200]
                )
            )
            if len(matched_lines) >= max_hits_per_file:
                matched_lines.append(
                    _("match.more", default="... (more matches in file)")
                )
                break

    if not matched_lines:
        s = max(0, m0.start() - 80)
        e = min(len(text), m0.end() + 80)
        excerpt = text[s:e].replace("\n", "\n").replace("\r", "\r")
        matched_lines.append(
            _("match.excerpt", default="MATCH: {text}").format(text=excerpt[:200])
        )

    return matched_lines


def _grep_text_streaming(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> list[str]:
    """For large files: stream line-by-line to keep memory usage bounded.

    Note: streaming mode cannot reliably provide an excerpt for cross-line matches.
    """

    with open(full_path, "rb") as f:
        head = f.read(8192)
    encodings = _ordered_encodings(_detect_text_encoding(head))
    if "utf-8" not in encodings:
        encodings.append("utf-8")

    for enc in encodings:
        matched_lines: list[str] = []
        line_num = 0
        try:
            with open(full_path, "r", encoding=enc, errors="strict") as f:
                for line in f:
                    line_num += 1
                    if regex.search(line):
                        matched_lines.append(
                            _("match.line", default="L{line}: {text}").format(
                                line=line_num, text=line.strip()[:200]
                            )
                        )
                        if len(matched_lines) >= max_hits_per_file:
                            matched_lines.append(
                                _("match.more", default="... (more matches in file)")
                            )
                            break
            return matched_lines
        except UnicodeDecodeError:
            continue
        except Exception:
            continue

    return []


def run_tool(args: dict[str, Any]) -> str:
    """Run file search."""

    try:
        root_path = args.get("path") or args.get("root_path") or "."
        name_pattern = args.get("name_pattern") or "*"
        content_pattern = args.get("content_pattern", "")
        case_sensitive = args.get("case_sensitive", False)
        max_results = args.get("max_results", 50)
        page = args.get("page", 1)
        fast_read_threshold_bytes = int(
            args.get("fast_read_threshold_bytes", 8_000_000)
        )

        # Normalize max_results and page
        try:
            max_results = int(max_results)
        except Exception:
            max_results = 50
        try:
            page = int(page)
            if page < 1:
                page = 1
        except Exception:
            page = 1

        if not os.path.exists(root_path):
            msg = _(
                "err.dir_not_exist",
                default="[search_files error] Directory does not exist: {path}",
            ).format(path=root_path)
            return _json_err(msg, root_path=root_path)

        # Compile content regex if provided
        regex: Optional[re.Pattern[str]] = None
        compiled_pattern_for_log = content_pattern

        if content_pattern:
            flags = 0 if case_sensitive else re.IGNORECASE

            normalized_pattern = _normalize_newline_tokens_in_pattern(content_pattern)
            compiled_pattern_for_log = normalized_pattern

            try:
                regex = re.compile(normalized_pattern, flags)
            except re.error as e:
                msg = _(
                    "err.regex_compile",
                    default="[search_files error] Failed to compile regex: {error}",
                ).format(error=str(e))
                return _json_err(msg)

        results = []

        if os.environ.get("UAGENT_SEARCH_FILES_DEBUG"):
            print(
                f"[search_files] root='{root_path}', name='{name_pattern}', grep='{compiled_pattern_for_log}'",
                file=sys.stderr,
            )

        for dirpath, dirnames, filenames in os.walk(root_path):
            # Filter excluded directories by mutating dirnames in-place.
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

            for fname in filenames:
                if (
                    regex is not None
                    and os.path.splitext(fname)[1].lower() in IGNORE_EXTS
                ):
                    continue

                full_path = os.path.join(dirpath, fname)

                # Match by relative path (supports patterns like 'No*/**/README*')
                rel = os.path.relpath(full_path, root_path).replace(os.sep, "/")
                if not fnmatch.fnmatch(rel, name_pattern):
                    continue

                # Content filtering
                matched_lines: list[str] = []
                if regex is not None:
                    try:
                        with open(full_path, "rb") as bf:
                            head = bf.read(8192)
                        if _looks_binary(head):
                            continue

                        # Choose strategy based on file size
                        size = os.path.getsize(full_path)
                        if size < fast_read_threshold_bytes:
                            with open(full_path, "rb") as bf:
                                data = bf.read()
                            if _looks_binary(data[:8192]):
                                continue
                            matched_lines = _grep_text_full_read_bytes(
                                data, regex, max_hits_per_file=5
                            )
                        else:
                            matched_lines = _grep_text_streaming(
                                full_path, regex, max_hits_per_file=5
                            )

                        if not matched_lines:
                            continue
                    except Exception:
                        # Skip unreadable files
                        continue

                rel = os.path.relpath(full_path, root_path)
                if matched_lines:
                    results.append({"file": rel, "matches": matched_lines})
                else:
                    results.append({"file": rel})

        if not results:
            return _(
                "out.no_match", default="[search_files] No files matched the criteria."
            )

        # Apply pagination
        from .pagination_util import paginate_results

        page_results, page, total_pages, total_results = paginate_results(
            results, page, max_results
        )

        out_lines: list[str] = []
        out_lines.append(
            _(
                "out.found_paginated",
                default="[search_files] Page {page} of {total_pages} (Total {total} results, showing {showing})",
            ).format(
                page=page,
                total_pages=total_pages,
                total=total_results,
                showing=len(page_results),
            )
        )

        for r in page_results:
            out_lines.append(
                _("out.file", default="File: {file}").format(file=r["file"])
            )
            for m in r.get("matches", [])[:10]:
                out_lines.append(f"  {m}")

        return "\n".join(out_lines)
    except Exception as e:
        return _json_err(
            f"[search_files error] {type(e).__name__}: {e}",
            exception=type(e).__name__,
        )
