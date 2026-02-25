# tools/search_files_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import os
import re
import fnmatch
from typing import Any, Dict, List

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


def _grep_text_full_read(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> List[str]:
    """For small/medium files: read the entire file and grep quickly."""

    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    if not regex.search(text):
        return []

    matched_lines: List[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if regex.search(line):
            matched_lines.append(f"L{i}: {line.strip()[:200]}")
            if len(matched_lines) >= max_hits_per_file:
                matched_lines.append("... (more matches in file)")
                break

    return matched_lines


def _grep_text_streaming(
    full_path: str,
    regex: re.Pattern[str],
    max_hits_per_file: int,
) -> List[str]:
    """For large files: stream line-by-line to keep memory usage bounded."""

    matched_lines: List[str] = []
    line_num = 0
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_num += 1
            if regex.search(line):
                matched_lines.append(f"L{line_num}: {line.strip()[:200]}")
                if len(matched_lines) >= max_hits_per_file:
                    matched_lines.append("... (more matches in file)")
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
        return f"[search_files error] Directory does not exist: {root_path}"

    # Compile content regex if provided
    regex = None
    if content_pattern:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(content_pattern, flags)
        except re.error as e:
            return f"[search_files error] Failed to compile regex: {e}"

    results = []
    count = 0
    truncated = False

    import sys

    print(
        f"[search_files] root='{root_path}', name='{name_pattern}', grep='{content_pattern}'",
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
                        matched_lines = _grep_text_full_read(full_path, regex, max_hits_per_file=5)
                    else:
                        matched_lines = _grep_text_streaming(full_path, regex, max_hits_per_file=5)

                    if not matched_lines:
                        continue
                except Exception as e:
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
        return "[search_files] No files matched the criteria."

    # Human-readable output (kept for compatibility with existing consumers)
    out_lines: List[str] = []
    if truncated:
        out_lines.append(f"[search_files] Found {len(results)} results (truncated to {max_results})")
    else:
        out_lines.append(f"[search_files] Found {len(results)} results")

    for r in results[:max_results]:
        out_lines.append(f"File: {r['file']}")
        for m in r.get("matches", [])[:10]:
            out_lines.append(f"  {m}")

    return "\n".join(out_lines)
