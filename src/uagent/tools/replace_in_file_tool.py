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
  sequence "\\n" (JSON: "\\\\n"). This tool will expand it to a real newline.
  Do NOT include raw newline characters (\n/\r) in JSON strings.
- For preview=false, the tool may require confirmation when there are many
  matches (confirm_if_matches_over).
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

from . import context
from .safe_file_ops_extras import ensure_within_workdir, make_backup_before_overwrite

BUSY_LABEL = True
STATUS_LABEL = "tool:replace_in_file"


def _make_summary(
    *,
    preview: bool,
    match_count: int | None = None,
    blocked: bool = False,
    reason: str | None = None,
    error: str | None = None,
) -> str:
    """Build a stable human-readable summary.

    Notes:
    - Keep wording stable because tests/assertions may rely on it.
    """

    if error is not None:
        return f"Error: {error}"

    mc = 0 if match_count is None else int(match_count)

    if blocked:
        if reason:
            return f"Blocked: {reason}"
        return f"Blocked: {mc}"

    if preview:
        return f"Preview: {mc} matches found" if mc else "Successfully no change (0 matches)"

    return "Successfully no change (0 matches)" if mc == 0 else f"{mc} match(es)"


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
                "- In both modes, the tool expands newline tokens \\r\\n/\\r/\\n to real newlines and normalizes to LF for matching.\n"
                "- In regex mode, replacement uses Python re semantics (\\1, \\2, ... for capture groups).\n\n"
                "Windows path note (especially when editing .py):\n"
                "- In Python string literals, backslashes must be escaped (e.g., C:\\\\path).\n\n"
                "Safety:\n"
                "- When preview=false and match_count >= confirm_if_matches_over, this tool will block."
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
                        default="When preview=false, block if the number of matches is >= this value.",
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
            },
            "required": ["path", "pattern", "replacement"],
        },
    },
}


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


def _expand_newline_tokens_to_lf(s: str) -> str:
    """Expand user-provided newline tokens and normalize to LF.

    Supports BOTH:
    - JSON/CLI escaped sequences (literal backslash tokens): "\\n", "\\r", "\\r\\n"
    - Pasted real newlines (actual '\n' or '\r')

    Output is normalized to LF ("\n").
    """

    lf = chr(10)
    cr = chr(13)
    crlf = cr + lf

    # 1) Literal backslash tokens
    s = s.replace(r"\\r\\n", crlf).replace(r"\\r", cr).replace(r"\\n", lf)

    # 2) Actual newlines
    s = s.replace(crlf, lf).replace(cr, lf)

    return s


@dataclass
class MatchHit:
    line_no: int
    col: int
    match_text: str
    before: str
    after: str


def _idx_to_line_col(line_starts: List[int], idx: int) -> Tuple[int, int]:
    """Map absolute idx to (1-based line_no, 0-based col)."""

    line_no = 1
    col = idx
    for i, off in enumerate(line_starts):
        if off <= idx:
            line_no = i + 1
            col = idx - off
        else:
            break
    return line_no, col


def _build_match_hits_literal(text: str, pat: str, max_hits: int = 100) -> List[MatchHit]:
    """Build match-based hits for literal mode.

    - Returns line/column (1-based line, 0-based column) and same-line context.
    - Does not try to interpret regex metacharacters.

    Notes:
    - Normalize CRLF/CR/LF to LF for stable index -> (line,col) mapping.
    - Preview is best-effort; we prioritize stability over exact preservation of original newlines.
    """

    if not pat:
        return []

    norm = text.replace("\r\n", "\n").replace("\r", "\n")

    line_starts: List[int] = [0]
    for m in re.finditer("\n", norm):
        line_starts.append(m.end())

    lines = norm.splitlines(keepends=False)

    hits: List[MatchHit] = []
    start = 0
    while True:
        idx = norm.find(pat, start)
        if idx < 0:
            break

        line_no, col = _idx_to_line_col(line_starts, idx)

        line = lines[line_no - 1] if 0 <= line_no - 1 < len(lines) else ""
        before = line[:col]
        after = line[col + len(pat) :]
        mtxt = pat if len(pat) <= 200 else pat[:200] + "..."

        hits.append(MatchHit(line_no=line_no, col=col, match_text=mtxt, before=before, after=after))
        if len(hits) >= max_hits:
            break

        start = idx + len(pat)  # non-overlapping

    return hits


def _build_match_hits_regex(text: str, pattern: str, max_hits: int = 100) -> List[MatchHit]:
    """Build match-based hits for regex mode using re.finditer.

    Notes:
    - Normalize CRLF/CR/LF to LF for stable index -> (line,col) mapping.
    - Preview is best-effort; we prioritize stability over exact preservation of original newlines.
    """

    try:
        rx = re.compile(pattern)
    except re.error:
        return []

    norm = text.replace("\r\n", "\n").replace("\r", "\n")

    line_starts: List[int] = [0]
    for m in re.finditer("\n", norm):
        line_starts.append(m.end())

    lines = norm.splitlines(keepends=False)

    hits: List[MatchHit] = []
    for m in rx.finditer(norm):
        idx = m.start()
        line_no, col = _idx_to_line_col(line_starts, idx)

        line = lines[line_no - 1] if 0 <= line_no - 1 < len(lines) else ""
        before = line[:col]
        after = line[col + max(0, m.end() - m.start()) :]

        mtxt = m.group(0)
        if len(mtxt) > 200:
            mtxt = mtxt[:200] + "..."

        hits.append(MatchHit(line_no=line_no, col=col, match_text=mtxt, before=before, after=after))
        if len(hits) >= max_hits:
            break

    return hits


def _run_tool_impl(args: Dict[str, Any]) -> str:
    """Implementation (may raise)."""

    path_in = str(args.get("path") or "")
    mode = str(args.get("mode") or "literal")
    pattern = args.get("pattern")
    replacement = args.get("replacement")
    count = args.get("count", None)
    preview = bool(args.get("preview", True))
    context_lines = int(args.get("context_lines", 2))
    confirm_if_matches_over = int(args.get("confirm_if_matches_over", 10))
    encoding = str(args.get("encoding") or "utf-8")

    if not path_in:
        raise ValueError("path is required")

    abs_path = ensure_within_workdir(path_in)

    if pattern is None:
        raise ValueError("pattern is required")
    if replacement is None:
        raise ValueError("replacement is required")

    callbacks = context.get_callbacks()
    max_bytes = getattr(callbacks, "read_file_max_bytes", 20_000_000)

    original, detected_newline, encoding_used = _read_text_robust(
        abs_path, encoding=encoding, max_bytes=int(max_bytes)
    )

    # Apply
    if mode == "literal":
        pat = _expand_newline_tokens_to_lf(str(pattern))
        rep = _expand_newline_tokens_to_lf(str(replacement))

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
            return json.dumps({"ok": False, "error": f"invalid regex: {e}"}, ensure_ascii=False)

    else:
        raise ValueError("mode must be 'literal' or 'regex'")

    diff = _unified_diff(path_in, original, replaced)

    # No-op: avoid touching the file (mtime churn) and avoid creating a backup.
    if original == replaced:
        return json.dumps(
            {
                "ok": True,
                "path": path_in,
                "mode": mode,
                "match_count": match_count,
                "changed": False,
                "preview": False,
                "diff": diff,
                "encoding": encoding_used,
                "detected_newline": detected_newline,
                "written": False,
                "summary": _make_summary(preview=False, match_count=match_count),
            },
            ensure_ascii=False,
        )

    # Preview response
    if preview:
        if mode == "literal":
            match_hits = _build_match_hits_literal(original, pat)
        else:
            match_hits = _build_match_hits_regex(original, str(pattern))

        return json.dumps(
            {
                "ok": True,
                "path": path_in,
                "mode": mode,
                "match_count": match_count,
                "changed": True,
                "preview": True,
                "diff": diff,
                "summary": _make_summary(preview=True, match_count=match_count),
                "encoding": encoding_used,
                "detected_newline": detected_newline,
                "match_hits": [
                    {
                        "line_no": h.line_no,
                        "col": h.col,
                        "match_text": h.match_text,
                        "before": h.before,
                        "after": h.after,
                    }
                    for h in match_hits
                ],
            },
            ensure_ascii=False,
        )

    # Confirm for large match counts
    if match_count >= confirm_if_matches_over:
        return json.dumps(
            {
                "ok": False,
                "blocked": True,
                "reason": f"too_many_matches: {match_count}",
                "confirm_if_matches_over": confirm_if_matches_over,
                "summary": _make_summary(
                    preview=False,
                    match_count=match_count,
                    blocked=True,
                    reason=f"too_many_matches: {match_count}",
                ),
            },
            ensure_ascii=False,
        )

    backup = make_backup_before_overwrite(abs_path)
    _write_text_robust(abs_path, replaced, encoding=encoding_used, newline=detected_newline)

    return json.dumps(
        {
            "ok": True,
            "path": path_in,
            "mode": mode,
            "match_count": match_count,
            "changed": True,
            "preview": False,
            "diff": diff,
            "backup": backup,
            "encoding": encoding_used,
            "detected_newline": detected_newline,
            "written": True,
            "summary": _make_summary(preview=False, match_count=match_count),
        },
        ensure_ascii=False,
    )


def run_tool(args: Dict[str, Any]) -> str:
    """Entry point (never raises; returns JSON)."""

    try:
        return _run_tool_impl(args)
    except Exception as e:
        et = e.__class__.__name__
        msg = str(e)

        if isinstance(e, FileNotFoundError):
            msg = f"file not found: {msg}"
        elif isinstance(e, PermissionError):
            msg = f"dangerous path: {msg}"

        return json.dumps(
            {
                "ok": False,
                "error": msg,
                "error_type": et,
                "summary": _make_summary(preview=False, error=msg),
            },
            ensure_ascii=False,
        )
