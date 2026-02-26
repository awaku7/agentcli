# tools/replace_in_file_tool.py
"""replace_in_file_tool

Safely performs literal or regular-expression replacements on an existing text file.

Newline handling
- The tool normalizes line endings internally and writes the file back using the
  original newline convention to reduce cross-OS churn.

Modes
- preview=true: returns only a preview (hit locations and context) and does not
  modify the file.
- preview=false: writes changes after creating a backup (.org/.orgN).

Safety notes
- If you need to express a newline in pattern/replacement, use the two-character
  sequence "\\n" (JSON: "\\\\n"). Do NOT include raw newline characters (\n/\r)
  in JSON strings.
- For preview=false, the tool may require confirmation (human_ask) when the
  target path is risky or when there are many matches.
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import difflib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .safe_file_ops_extras import (
    ensure_within_workdir,
    make_backup_before_overwrite,
)

BUSY_LABEL = True
STATUS_LABEL = "tool:replace_in_file"


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "replace_in_file",
        "description": _(
            "tool.description",
            default=(
                "Perform literal or regular-expression replacements on a text file. "
                "Line endings are normalized internally, so patterns/replacements that include "
                "newlines are supported.\n\n"
                "Important (read carefully):\n"
                "- Always run with preview=true first to inspect hit locations and the diff preview.\n"
                "- Do NOT include raw newline characters in pattern/replacement. Use the two-character "
                "sequence \\n instead (JSON: \\\\n). Raw newlines can corrupt source files (e.g., Python string literals).\n"
                "- When mode=regex, pattern is interpreted as a Python re pattern (not a plain substring). "
                "For example, \\x is invalid; write \\xNN (e.g., \\x00, \\x1b).\n"
                "- If you only need to match a backslash literally, prefer mode=literal.\n"
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool performs literal or regex replacements on a text file.\n\n"
                "Recommended workflow:\n"
                "1) Inspect the target area with read_file\n"
                "2) Run replace_in_file with preview=true and verify hit locations + diff\n"
                "3) If correct, apply with preview=false (a .org/.orgN backup will be created)\n"
                "4) If you edited a .py file, run python -m py_compile for a syntax check\n\n"
                "Newlines (most important):\n"
                "- Do not include raw newlines in JSON strings.\n"
                "  - OK: aaa\\nbbb (JSON: aaa\\\\nbbb)\n"
                "  - NG: aaa<newline>bbb (can break source files and cause SyntaxError)\n\n"
                "Regex notes:\n"
                "- pattern is a Python re pattern\n"
                "- \\x is invalid (re.error); use \\xNN (e.g., \\x00)\n"
                "- Use mode=literal if you only need plain substring matching\n"
                "- In replacement, \\1, \\2, ... refer to capture groups; referencing a non-existent group is an error\n"
                "- In replacement, \\n means a backslash + n, not an actual newline\n\n"
                "Windows path note (especially when editing .py):\n"
                "- In Python string literals, backslashes must be escaped (e.g., C:\\\\path).\n\n"
                "Safety:\n"
                "- When preview=false and the operation is risky (dangerous path, many matches, etc.), "
                "the tool may require confirmation or cancel automatically."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Target file path (recommended: under workdir).",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["literal", "regex"],
                    "description": _(
                        "param.mode.description",
                        default="Replacement mode: literal (plain) or regex (Python re).",
                    ),
                    "default": "literal",
                },
                "pattern": {
                    "type": "string",
                    "description": _(
                        "param.pattern.description",
                        default="Search pattern. To express a newline, write \\n (JSON: \\\\n).",
                    ),
                },
                "replacement": {
                    "type": "string",
                    "description": _(
                        "param.replacement.description",
                        default="Replacement text.",
                    ),
                },
                "count": {
                    "type": ["integer", "null"],
                    "description": _(
                        "param.count.description",
                        default="Maximum number of replacements. If null, replace all matches.",
                    ),
                    "default": None,
                },
                "preview": {
                    "type": "boolean",
                    "description": _(
                        "param.preview.description",
                        default="If true, return a preview only and do not modify the file.",
                    ),
                    "default": True,
                },
                "context_lines": {
                    "type": "integer",
                    "description": _(
                        "param.context_lines.description",
                        default="Number of context lines to include before/after each hit in the preview.",
                    ),
                    "default": 2,
                },
                "confirm_if_matches_over": {
                    "type": "integer",
                    "description": _(
                        "param.confirm_if_matches_over.description",
                        default="When preview=false, require confirmation if the number of matches is >= this value.",
                    ),
                    "default": 10,
                },
                "encoding": {
                    "type": "string",
                    "description": _(
                        "param.encoding.description",
                        default="File encoding (default: utf-8).",
                    ),
                    "default": "utf-8",
                },
                "raw_newline_policy": {
                    "type": "string",
                    "enum": ["allow", "reject"],
                    "description": _(
                        "param.raw_newline_policy.description",
                        default=(
                            "How to handle raw newline characters (\\n/\\r) in pattern/replacement. "
                            "allow=permit, reject=cancel automatically (no confirmation)."
                        ),
                    ),
                    "default": "allow",
                },
            },
            "required": ["path", "pattern", "replacement"],
        },
    },
}


@dataclass
class PreviewHit:
    line_no: int
    before_lines: List[str]
    line_before: str
    line_after: str
    after_lines: List[str]


def _read_text_robust(path: str, encoding: str, max_bytes: int) -> Tuple[str, Any, str]:
    """Read a text file and return (content, detected_newlines, encoding_used)."""

    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"file too large: {size} > {max_bytes} bytes")

    def try_read(enc: str, errors: str) -> Tuple[str, Any, str]:
        with open(path, "r", encoding=enc, errors=errors, newline=None) as f:
            content = f.read()
            return content, f.newlines, enc

    try:
        return try_read(encoding, "strict")
    except (UnicodeDecodeError, LookupError):
        return try_read("utf-8", "replace")


def _unified_diff(path: str, original: str, replaced: str) -> str:
    """Return unified diff string ("" if no changes)."""

    if original == replaced:
        return ""

    a = original.splitlines(True)
    b = replaced.splitlines(True)
    diff = difflib.unified_diff(a, b, fromfile=f"a/{path}", tofile=f"b/{path}")
    return "".join(diff)


def _write_text_robust(path: str, text: str, encoding: str, newline: Any) -> None:
    """Write text back using the original newline convention."""

    # Normalize in-memory newlines to \n (avoid mixed newlines)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # If mixed newlines were detected, prefer CRLF.
    if isinstance(newline, tuple):
        target_newline = "\r\n" if "\r\n" in newline else newline[0]
    else:
        target_newline = newline or "\n"

    with open(path, "w", encoding=encoding, newline=target_newline) as f:
        f.write(text)


def _build_preview(
    original: str, replaced: str, context_lines: int, max_hits: int = 100
) -> List[PreviewHit]:
    """Build a list of PreviewHit objects using difflib."""

    orig_lines_raw = original.splitlines(keepends=True)
    new_lines_raw = replaced.splitlines(keepends=True)

    # For matching: normalize line-endings by stripping trailing \r?\n.
    orig_lines = [ln.rstrip("\r\n") for ln in orig_lines_raw]
    new_lines = [ln.rstrip("\r\n") for ln in new_lines_raw]

    matcher = difflib.SequenceMatcher(None, orig_lines, new_lines)
    hits: List[PreviewHit] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        # Start line of the change (1-based)
        line_no = i1 + 1

        start = max(0, i1 - context_lines)
        end = min(len(orig_lines_raw), i2 + context_lines)

        before_lines = [ln.rstrip("\r\n") for ln in orig_lines_raw[start:i1]]
        after_lines = [ln.rstrip("\r\n") for ln in orig_lines_raw[i2:end]]

        line_before = orig_lines[i1] if i1 < len(orig_lines) else ""
        line_after = new_lines[j1] if j1 < len(new_lines) else ""

        hits.append(
            PreviewHit(
                line_no=line_no,
                before_lines=before_lines,
                line_before=line_before,
                line_after=line_after,
                after_lines=after_lines,
            )
        )

        if len(hits) >= max_hits:
            break

    return hits


def run_tool(args: Dict[str, Any]) -> str:
    """Entry point."""
    path_in = str(args.get("path") or "")
    mode = str(args.get("mode") or "literal")
    pattern = args.get("pattern")
    replacement = args.get("replacement")
    count = args.get("count", None)
    preview = bool(args.get("preview", True))
    context_lines = int(args.get("context_lines", 2))
    confirm_if_matches_over = int(args.get("confirm_if_matches_over", 10))
    encoding = str(args.get("encoding") or "utf-8")
    raw_newline_policy = str(args.get("raw_newline_policy") or "allow")
    if not path_in:
        raise ValueError("path is required")

    # Resolve and validate path within workdir
    abs_path = ensure_within_workdir(path_in)
    if pattern is None:
        raise ValueError("pattern is required")

    if replacement is None:
        raise ValueError("replacement is required")

    if raw_newline_policy not in ("allow", "reject"):
        raise ValueError("raw_newline_policy must be 'allow' or 'reject'")
    # Read
    original, detected_newline, encoding_used = _read_text_robust(
        abs_path, encoding=encoding, max_bytes=20_000_000
    )

    # Reject raw newlines in pattern/replacement if requested.
    if raw_newline_policy == "reject":
        if (
            ("\n" in str(pattern))
            or ("\r" in str(pattern))
            or ("\n" in str(replacement))
            or ("\r" in str(replacement))
        ):
            return json.dumps(
                {
                    "ok": False,
                    "blocked": True,
                    "reason": "raw_newline_rejected",
                },
                ensure_ascii=False,
            )

    # Apply
    if mode == "literal":
        pat = str(pattern)
        rep = str(replacement)
        # Non-overlapping occurrences (same semantics as str.replace)
        occ = original.count(pat)
        if count is None:
            match_count = occ
            replaced = original.replace(pat, rep)
        else:
            limit = int(count)
            if limit < 0:
                limit = 0
            match_count = min(occ, limit)
            replaced = original.replace(pat, rep, limit)
    elif mode == "regex":
        try:
            replaced, n = re.subn(
                str(pattern),
                str(replacement),
                original,
                count=0 if count is None else int(count),
            )
            match_count = int(n)
        except re.error as e:
            return json.dumps(
                {"ok": False, "error": f"invalid regex pattern: {e}"},
                ensure_ascii=False,
            )
    else:
        raise ValueError("mode must be 'literal' or 'regex'")

    diff = _unified_diff(path_in, original, replaced)

    # Preview response
    if preview:
        hits = _build_preview(original, replaced, context_lines=context_lines)
        return json.dumps(
            {
                "ok": True,
                "path": path_in,
                "mode": mode,
                "match_count": match_count,
                "changed": original != replaced,
                "preview": True,
                "diff": diff,
                "encoding": encoding_used,
                "detected_newline": detected_newline,
                "hits": [
                    {
                        "line_no": h.line_no,
                        "before_lines": h.before_lines,
                        "line_before": h.line_before,
                        "line_after": h.line_after,
                        "after_lines": h.after_lines,
                    }
                    for h in hits
                ],
            },
            ensure_ascii=False,
        )

    # Confirm for large match counts
    # (The framework may also enforce confirmations.)
    # We approximate match count by the number of hunks in the preview.
    hits = _build_preview(original, replaced, context_lines=context_lines)
    if len(hits) >= confirm_if_matches_over:
        return json.dumps(
            {
                "ok": False,
                "blocked": True,
                "reason": f"too_many_matches: {len(hits)}",
                "confirm_if_matches_over": confirm_if_matches_over,
            },
            ensure_ascii=False,
        )

    # Backup and write
    backup = make_backup_before_overwrite(abs_path)
    _write_text_robust(
        abs_path, replaced, encoding=encoding_used, newline=detected_newline
    )

    return json.dumps(
        {
            "ok": True,
            "path": path_in,
            "mode": mode,
            "match_count": match_count,
            "changed": original != replaced,
            "preview": False,
            "diff": diff,
            "backup": backup,
            "encoding": encoding_used,
            "detected_newline": detected_newline,
            "written": True,
        },
        ensure_ascii=False,
    )
