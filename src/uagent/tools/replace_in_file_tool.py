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
        return (
            f"Preview: {mc} matches found"
            if mc
            else "Successfully no change (0 matches)"
        )

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
                "ABSOLUTE RULES (must follow):\n"
                "1) ALWAYS run replace_in_file with preview=true first (never skip).\n"
                "2) NEVER include raw newlines in JSON strings. Use \\n (JSON: \\\\n).\n"
                "3) Use mode=literal unless you truly need regex.\n\n"
                "Regex quick notes (only if mode=regex):\n"
                "- pattern is Python re; . * ? [ ] ( ) ^ $ are special\n"
                "- \\x is invalid; use \\xNN (e.g., \\x00)\n"
                "- replacement \\1, \\2... refer to capture groups\n"
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "ABSOLUTE RULES (must follow):\n"
                "1) ALWAYS run replace_in_file with preview=true first (never skip).\n"
                "2) NEVER include raw newlines in JSON strings. Use \\n (JSON: \\\\n).\n"
                "3) Use mode=literal unless you truly need regex.\n\n"
                "Workflow:\n"
                "1) read_file to inspect\n"
                "2) replace_in_file preview=true and verify hit locations + diff\n"
                "3) replace_in_file preview=false to apply (backup .org/.orgN)\n\n"
                "Regex quick notes (only if mode=regex):\n"
                "- pattern is Python re; . * ? [ ] ( ) ^ $ are special\n"
                "- \\x is invalid; use \\xNN (e.g., \\x00)\n"
                "- replacement \\1, \\2... refer to capture groups\n"
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expand_newline_tokens": {
                    "type": "boolean",
                    "description": _(
                        "param.expand_newline_tokens.description",
                        default=(
                            "If true (default), expands newline tokens (\\r\\n/\\r/\\n) into real newlines for matching/replacement. "
                            "If false, treats them as literal characters (e.g., the two characters \\ and n)."
                        ),
                    ),
                    "default": True,
                },
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
                        default="Search pattern. To express a newline, write \\n (JSON: \\\n).",
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
    """Return unified diff string (""" """ if no changes)."""

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

    - \r\n / \r / \n (literal tokens) are converted into actual newlines.
    - Result uses LF (\n) only.
    """

    # Convert user tokens into real newlines.
    s = s.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")

    # Normalize any actual CRLF/CR that may have been present.
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


@dataclass
class _Hit:
    start: int
    end: int


def _map_idx_to_line_col(text: str, idx: int) -> Tuple[int, int]:
    """Map absolute idx to (1-based line_no, 0-based col)."""

    if idx < 0:
        idx = 0
    if idx > len(text):
        idx = len(text)

    # Count newlines before idx.
    line_no = text.count("\n", 0, idx) + 1
    last_nl = text.rfind("\n", 0, idx)
    col = idx if last_nl < 0 else idx - last_nl - 1
    return line_no, col


def _extract_same_line_context(text: str, start: int, end: int) -> Tuple[str, str, str]:
    """Extract (before, match, after) on the same line for a hit."""

    # Find line boundaries
    line_start = text.rfind("\n", 0, start)
    line_start = 0 if line_start < 0 else line_start + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end

    before = text[line_start:start]
    match = text[start:end]
    after = text[end:line_end]
    return before, match, after


def _find_hits_literal(haystack: str, needle: str) -> List[_Hit]:
    hits: List[_Hit] = []
    if needle == "":
        return hits

    start = 0
    while True:
        pos = haystack.find(needle, start)
        if pos < 0:
            break
        hits.append(_Hit(pos, pos + len(needle)))
        start = pos + len(needle)
    return hits


def _find_hits_regex(haystack: str, pattern: re.Pattern[str]) -> List[_Hit]:
    hits: List[_Hit] = []
    for m in pattern.finditer(haystack):
        hits.append(_Hit(m.start(), m.end()))
    return hits


def _apply_replacements_literal(
    text: str, pattern: str, replacement: str, count: int | None
) -> Tuple[str, int]:
    if count is None:
        return text.replace(pattern, replacement), text.count(pattern) if pattern else 0

    # Manual limited replace
    out = text
    n = 0
    start = 0
    while n < count:
        pos = out.find(pattern, start)
        if pos < 0:
            break
        out = out[:pos] + replacement + out[pos + len(pattern) :]
        start = pos + len(replacement)
        n += 1
    return out, n


def run_tool(args: Dict[str, Any]) -> str:
    cb = context.get_callbacks()

    try:
        path = str(args.get("path") or "")
        mode = str(args.get("mode") or "literal")
        pattern = str(args.get("pattern") or "")
        replacement = str(args.get("replacement") or "")
        preview = bool(args.get("preview", True))
        # context_lines is intentionally accepted for API compatibility
        # (not used by the tool implementation)
        # context_lines = int(args.get("context_lines", 2))
        confirm_if_matches_over = int(args.get("confirm_if_matches_over", 10))
        count = args.get("count")
        encoding = str(args.get("encoding") or "utf-8")
        expand_newline_tokens = bool(args.get("expand_newline_tokens", True))

        if not path:
            return json.dumps(
                {"ok": False, "error": "[replace_in_file error] path is not specified"},
                ensure_ascii=False,
            )

        # Safety: ensure path within workdir
        ensure_within_workdir(path)

        # Normalize/expand newline tokens for matching/replacement
        if expand_newline_tokens:
            pattern2 = _expand_newline_tokens_to_lf(pattern)
            replacement2 = _expand_newline_tokens_to_lf(replacement)
        else:
            pattern2 = pattern
            replacement2 = replacement

        max_bytes = cb.read_file_max_bytes
        original, detected_newline, encoding_used = _read_text_robust(
            path, encoding, max_bytes
        )

        # Normalize original in-memory
        original_norm = original.replace("\r\n", "\n").replace("\r", "\n")

        match_count: int
        replaced: str
        match_hits: List[Dict[str, Any]] = []

        if mode == "regex":
            try:
                rx = re.compile(pattern2)
            except re.error as e:
                return json.dumps(
                    {"ok": False, "error": f"[replace_in_file error] re.error: {e}"},
                    ensure_ascii=False,
                )

            # Count matches
            hits = _find_hits_regex(original_norm, rx)
            match_count = len(hits)

            # Apply replacement (Python re semantics)
            try:
                if count is None:
                    replaced = rx.sub(replacement2, original_norm)
                else:
                    replaced = rx.sub(replacement2, original_norm, count=int(count))
            except re.error as e:
                return json.dumps(
                    {
                        "ok": False,
                        "error": f"[replace_in_file error] re.error during replacement: {e}",
                    },
                    ensure_ascii=False,
                )

            # Preview hit locations (same-line context)
            for h in hits[:50]:
                line_no, col = _map_idx_to_line_col(original_norm, h.start)
                before, match, after = _extract_same_line_context(
                    original_norm, h.start, h.end
                )
                match_hits.append(
                    {
                        "line_no": line_no,
                        "col": col,
                        "match_text": match,
                        "before": before[-200:],
                        "after": after[:200],
                    }
                )

        else:
            # literal
            hits = _find_hits_literal(original_norm, pattern2)
            match_count = len(hits)

            replaced, _repl_count = _apply_replacements_literal(
                original_norm,
                pattern2,
                replacement2,
                None if count is None else int(count),
            )

            for h in hits[:50]:
                line_no, col = _map_idx_to_line_col(original_norm, h.start)
                before, match, after = _extract_same_line_context(
                    original_norm, h.start, h.end
                )
                match_hits.append(
                    {
                        "line_no": line_no,
                        "col": col,
                        "match_text": match,
                        "before": before[-200:],
                        "after": after[:200],
                    }
                )

        changed = replaced != original_norm
        diff = _unified_diff(path, original_norm, replaced)

        # Block when applying too many matches
        if not preview and match_count >= confirm_if_matches_over:
            return json.dumps(
                {
                    "ok": True,
                    "path": path,
                    "mode": mode,
                    "match_count": match_count,
                    "changed": False,
                    "preview": preview,
                    "diff": diff,
                    "encoding": encoding_used,
                    "detected_newline": (
                        "\n" if detected_newline is None else detected_newline
                    ),
                    "written": False,
                    "summary": _make_summary(
                        preview=preview,
                        match_count=match_count,
                        blocked=True,
                        reason=f"match_count {match_count} >= confirm_if_matches_over {confirm_if_matches_over}",
                    ),
                    "match_hits": match_hits,
                },
                ensure_ascii=False,
            )

        written = False
        backup_path: str | None = None
        if not preview and changed:
            backup_path = make_backup_before_overwrite(path)
            _write_text_robust(path, replaced, encoding_used, detected_newline)
            written = True

        result: Dict[str, Any] = {
            "ok": True,
            "path": path,
            "mode": mode,
            "match_count": match_count,
            "changed": changed,
            "preview": preview,
            "diff": diff,
            "encoding": encoding_used,
            "detected_newline": "\n" if detected_newline is None else detected_newline,
            "written": written,
            "summary": _make_summary(preview=preview, match_count=match_count),
        }
        if backup_path is not None:
            result["backup"] = backup_path
        if match_hits:
            result["match_hits"] = match_hits

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"[replace_in_file error] {type(e).__name__}: {e}",
                "exception": type(e).__name__,
            },
            ensure_ascii=False,
        )
