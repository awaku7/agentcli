# tools/search_files_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import fnmatch
import os
import re
from typing import Any, Dict, List, Optional

# Mark as busy while running
BUSY_LABEL = True
STATUS_LABEL = "tool:search_files"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_files",
        "description": _(
            "tool.description",
            default="Search files under a directory by name pattern (glob) and/or by content (regex).",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Search for files under a directory. You can filter by filename pattern (glob) and optionally "
                "grep file contents using a regular expression.\n\n"
                "Notes:\n"
                "- content_pattern is treated as a Python regular expression.\n"
                "- If content_pattern is empty, only filename matching is performed.\n"
                "- For performance and safety, binary-like files can be excluded from content searching."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "root_path": {
                    "type": "string",
                    "description": _(
                        "param.root_path.description",
                        default="Root directory to start searching from (default: current directory).",
                    ),
                },
                "name_pattern": {
                    "type": "string",
                    "description": _(
                        "param.name_pattern.description",
                        default=(
                            "Filename glob pattern (e.g., '*.py', 'test_*'). If omitted, all files are considered."
                        ),
                    ),
                },
                "content_pattern": {
                    "type": "string",
                    "description": _(
                        "param.content_pattern.description",
                        default=(
                            "Regular expression to search within files. If provided, only files containing at least one "
                            "matching line are returned."
                        ),
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
                        default="Maximum number of matched files to return (default: 50).",
                    ),
                },
                "exclude_binary": {
                    "type": "boolean",
                    "description": _(
                        "param.exclude_binary.description",
                        default=(
                            "When content_pattern is set, exclude files that appear to be binary (default: true)."
                        ),
                    ),
                    "default": True,
                },
                "binary_sniff_bytes": {
                    "type": "integer",
                    "description": _(
                        "param.binary_sniff_bytes.description",
                        default="Number of leading bytes used to detect binary-like files (default: 8192).",
                    ),
                    "default": 8192,
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

# File extensions to exclude (typically binary or large assets)
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
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
}


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


def _grep_text_full_read(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> List[str]:
    """For small/medium files: read the entire file and grep quickly."""

    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    m0 = regex.search(text)
    if not m0:
        return []

    matched_lines: List[str] = []
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


def _grep_text_streaming(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> List[str]:
    """For large files: stream line-by-line to keep memory usage bounded.

    Note: streaming mode cannot reliably provide an excerpt for cross-line matches.
    """

    matched_lines: List[str] = []
    line_num = 0
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
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


def run_tool(args: Dict[str, Any]) -> str:
    """Run file search."""

    root_path = args.get("root_path") or "."
    name_pattern = args.get("name_pattern") or "*"
    content_pattern = args.get("content_pattern", "")
    case_sensitive = args.get("case_sensitive", False)
    max_results = args.get("max_results", 50)
    exclude_binary = bool(args.get("exclude_binary", True))
    binary_sniff_bytes = int(args.get("binary_sniff_bytes", 8192))
    fast_read_threshold_bytes = int(args.get("fast_read_threshold_bytes", 8_000_000))

    # Normalize max_results
    try:
        max_results = int(max_results)
    except Exception:
        max_results = 50

    if not os.path.exists(root_path):
        return _(
            "err.dir_not_exist",
            default="[search_files error] Directory does not exist: {path}",
        ).format(path=root_path)

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
            return _(
                "err.regex_compile",
                default="[search_files error] Failed to compile regex: {error}",
            ).format(error=str(e))

    results = []
    count = 0
    truncated = False

    import sys

    print(
        f"[search_files] root='{root_path}', name='{name_pattern}', grep='{compiled_pattern_for_log}'",
        file=sys.stderr,
    )

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter excluded directories by mutating dirnames in-place.
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for fname in filenames:
            if os.path.splitext(fname)[1].lower() in IGNORE_EXTS:
                continue

            if not fnmatch.fnmatch(fname, name_pattern):
                continue

            full_path = os.path.join(dirpath, fname)

            # Content filtering
            matched_lines: List[str] = []
            if regex is not None:
                try:
                    with open(full_path, "rb") as bf:
                        head = bf.read(binary_sniff_bytes)
                    if exclude_binary and _looks_binary(head):
                        continue

                    # Choose strategy based on file size
                    size = os.path.getsize(full_path)
                    if size < fast_read_threshold_bytes:
                        matched_lines = _grep_text_full_read(
                            full_path, regex, max_hits_per_file=5
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

            count += 1
            if count >= max_results:
                truncated = True
                break

        if truncated:
            break

    if not results:
        return _(
            "out.no_match", default="[search_files] No files matched the criteria."
        )

    # Human-readable output (kept for compatibility with existing consumers)
    out_lines: List[str] = []
    if truncated:
        out_lines.append(
            _(
                "out.found_truncated",
                default="[search_files] Found {n} results (truncated to {max_results})",
            ).format(n=len(results), max_results=max_results)
        )
    else:
        out_lines.append(
            _("out.found", default="[search_files] Found {n} results").format(
                n=len(results)
            )
        )

    for r in results[:max_results]:
        out_lines.append(_("out.file", default="File: {file}").format(file=r["file"]))
        for m in r.get("matches", [])[:10]:
            out_lines.append(f"  {m}")

    return "\n".join(out_lines)
