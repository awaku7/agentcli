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
  matches (confirm_over).
"""

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

import difflib
import hashlib
import json
import os
from pathlib import Path
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
                "Guidelines:\n"
                "- Recommended: Run with preview=true first to verify hit locations and diff.\n"
                "- Never include raw newlines in JSON strings; use \\n (JSON: \\\n).\n"
                "- Use mode=literal unless regex is necessary.\n\n"
                "Regex notes (mode=regex):\n"
                "- pattern is Python re; . * ? [ ] ( ) ^ $ are special\n"
                "- \\x is invalid; use \\xNN (e.g., \\x00)\n"
                "- replacement \\1, \\2... refer to capture groups\n"
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Guidelines:\n"
                "- Recommended: Run with preview=true first to verify hit locations and diff.\n"
                "- Never include raw newlines in JSON strings; use \\n (JSON: \\\n).\n"
                "- Use mode=literal unless regex is necessary.\n\n"
                "Regex notes (mode=regex):\n"
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
                "preview": {
                    "type": "boolean",
                    "description": _(
                        "param.preview.description",
                        default="If true, return a preview only and do not modify the file.",
                    ),
                    "default": True,
                },
                "occurrence": {
                    "type": "integer",
                    "description": _(
                        "param.occurrence.description",
                        default="Which occurrence to replace (1-based). 0 means replace all occurrences.",
                    ),
                    "default": 0,
                },
                "confirm_over": {
                    "type": "integer",
                    "description": _(
                        "param.confirm_over.description",
                        default="When preview=false, block if the number of matches is greater than this value.",
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
                "return_hashes": {
                    "type": "boolean",
                    "description": _(
                        "param.return_hashes.description",
                        default="If true, include sha256_before and sha256_after in the result.",
                    ),
                    "default": False,
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "replace",
                        "append",
                        "insert_at_end",
                        "insert_before",
                        "insert_after",
                        "insert_at_line",
                        "replace_all_in_files",
                    ],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Operation: replace (default), append/insert_at_end, insert_before, insert_after, insert_at_line, or replace_all_in_files."
                        ),
                    ),
                    "default": "replace",
                },
                "line_no": {
                    "type": "integer",
                    "description": _(
                        "param.line_no.description",
                        default="1-based line number used by insert_at_line.",
                    ),
                    "default": 0,
                },
                "name_pattern": {
                    "type": "string",
                    "description": _(
                        "param.name_pattern.description",
                        default="Glob pattern used by replace_all_in_files (default: '*').",
                    ),
                    "default": "*",
                },
                "recursive": {
                    "type": "boolean",
                    "description": _(
                        "param.recursive.description",
                        default="When replace_all_in_files is used, recursively scan under the target directory (default: true).",
                    ),
                    "default": True,
                },
            },
            "required": ["path", "replacement"],
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
    """Return unified diff string, or an empty string if no changes."""

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


def _find_regex_match_by_occurrence(
    haystack: str, pattern: re.Pattern[str], occurrence: int
):
    if occurrence < 1:
        return None
    for idx, m in enumerate(pattern.finditer(haystack), start=1):
        if idx == occurrence:
            return m
    return None


def _apply_replacements_literal(
    text: str, pattern: str, replacement: str
) -> Tuple[str, int]:
    replaced = text.replace(pattern, replacement)
    return replaced, text.count(pattern) if pattern else 0


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_tool(args: Dict[str, Any]) -> str:
    cb = context.get_callbacks()

    def _normalize_lf(s: str) -> str:
        return s.replace("\r\n", "\n").replace("\r", "\n")

    def _find_hit_by_occurrence(hits: List[_Hit], occurrence: int) -> _Hit | None:
        if not hits:
            return None
        if occurrence <= 0:
            return hits[0]
        if occurrence > len(hits):
            return None
        return hits[occurrence - 1]

    def _insert_at_line(text: str, insertion: str, line_no: int) -> Tuple[str, int]:
        if line_no < 1:
            raise ValueError("line_no must be >= 1")
        lines = text.splitlines(True)
        if line_no > len(lines) + 1:
            raise ValueError(f"line_no out of range: {line_no} > {len(lines) + 1}")
        offset = sum(len(line) for line in lines[: line_no - 1])
        return text[:offset] + insertion + text[offset:], offset

    def _is_probably_binary(file_path: str, sample_size: int = 4096) -> bool:
        try:
            with open(file_path, 'rb') as f:
                return b"\x00" in f.read(sample_size)
        except OSError:
            return False

    def _single_file_edit(
        *,
        path: str,
        action: str,
        mode: str,
        pattern: str,
        replacement: str,
        preview: bool,
        occurrence: int,
        confirm_over: int,
        encoding: str,
        expand_newline_tokens: bool,
        return_hashes: bool,
        line_no: int,
    ) -> Dict[str, Any]:
        ensure_within_workdir(path)

        max_bytes = cb.read_file_max_bytes
        original, detected_newline, encoding_used = _read_text_robust(path, encoding, max_bytes)
        original_norm = _normalize_lf(original)
        before_sha = _sha256_file(path)
        after_sha = before_sha

        if expand_newline_tokens:
            pattern2 = _expand_newline_tokens_to_lf(pattern)
            replacement2 = _expand_newline_tokens_to_lf(replacement)
        else:
            pattern2 = pattern
            replacement2 = replacement

        match_count = 0
        replaced_count = 0
        replaced = original_norm
        match_hits: List[Dict[str, Any]] = []
        action_norm = {"append": "insert_at_end", "insert_at_end": "insert_at_end"}.get(action, action)

        if action_norm == "replace":
            if mode == "regex":
                try:
                    rx = re.compile(pattern2)
                except re.error as e:
                    raise ValueError(f"[replace_in_file error] re.error: {e}") from e

                hits = _find_hits_regex(original_norm, rx)
                match_count = len(hits)
                if occurrence == 0:
                    try:
                        replaced, replaced_count = rx.subn(replacement2, original_norm)
                    except re.error as e:
                        raise ValueError(f"[replace_in_file error] re.error during replacement: {e}") from e
                else:
                    m = _find_regex_match_by_occurrence(original_norm, rx, occurrence)
                    if m is None:
                        replaced_count = 0
                    else:
                        try:
                            repl = m.expand(replacement2)
                        except re.error as e:
                            raise ValueError(f"[replace_in_file error] re.error during replacement: {e}") from e
                        replaced = original_norm[: m.start()] + repl + original_norm[m.end() :]
                        replaced_count = 1
                for h in hits[:50]:
                    line_no2, col = _map_idx_to_line_col(original_norm, h.start)
                    before, match, after = _extract_same_line_context(original_norm, h.start, h.end)
                    match_hits.append(
                        {
                            "line_no": line_no2,
                            "col": col,
                            "match_text": match,
                            "before": before[-200:],
                            "after": after[:200],
                        }
                    )
            else:
                hits = _find_hits_literal(original_norm, pattern2)
                match_count = len(hits)
                if occurrence == 0:
                    replaced, replaced_count = _apply_replacements_literal(original_norm, pattern2, replacement2)
                else:
                    if occurrence > len(hits):
                        replaced_count = 0
                    else:
                        h = hits[occurrence - 1]
                        replaced = original_norm[: h.start] + replacement2 + original_norm[h.end :]
                        replaced_count = 1
                for h in hits[:50]:
                    line_no2, col = _map_idx_to_line_col(original_norm, h.start)
                    before, match, after = _extract_same_line_context(original_norm, h.start, h.end)
                    match_hits.append(
                        {
                            "line_no": line_no2,
                            "col": col,
                            "match_text": match,
                            "before": before[-200:],
                            "after": after[:200],
                        }
                    )

        elif action_norm in {"insert_before", "insert_after"}:
            if pattern2 == "":
                raise ValueError("[replace_in_file error] pattern must not be empty")
            if mode == "regex":
                try:
                    rx = re.compile(pattern2)
                except re.error as e:
                    raise ValueError(f"[replace_in_file error] re.error: {e}") from e
                hits = _find_hits_regex(original_norm, rx)
            else:
                hits = _find_hits_literal(original_norm, pattern2)
            match_count = len(hits)
            target_hit = _find_hit_by_occurrence(hits, occurrence)
            if target_hit is not None:
                if action_norm == "insert_before":
                    line_start = original_norm.rfind("\n", 0, target_hit.start)
                    line_start = 0 if line_start < 0 else line_start + 1
                    insert_at = line_start
                else:
                    line_end = original_norm.find("\n", target_hit.end)
                    insert_at = len(original_norm) if line_end < 0 else line_end + 1
                replaced = original_norm[:insert_at] + replacement2 + original_norm[insert_at:]
                replaced_count = 1
            for h in hits[:50]:
                line_no2, col = _map_idx_to_line_col(original_norm, h.start)
                before, match, after = _extract_same_line_context(original_norm, h.start, h.end)
                match_hits.append(
                    {
                        "line_no": line_no2,
                        "col": col,
                        "match_text": match,
                        "before": before[-200:],
                        "after": after[:200],
                    }
                )

        elif action_norm == "insert_at_line":
            replaced, _ = _insert_at_line(original_norm, replacement2, line_no)
            replaced_count = 1 if replaced != original_norm else 0
            match_count = replaced_count

        elif action_norm == "insert_at_end":
            replaced = original_norm + replacement2
            replaced_count = 1 if replaced != original_norm else 0
            match_count = replaced_count

        else:
            raise ValueError(f"[replace_in_file error] unsupported action: {action}")

        changed = replaced != original_norm
        diff = _unified_diff(path, original_norm, replaced)

        if not preview and action_norm == "replace" and occurrence == 0 and match_count > confirm_over:
            result = {
                "ok": True,
                "path": path,
                "action": action_norm,
                "mode": mode,
                "occurrence": occurrence,
                "line_no": line_no,
                "match_count": match_count,
                "replaced_count": replaced_count,
                "changed": False,
                "preview": preview,
                "diff": diff,
                "encoding": encoding_used,
                "detected_newline": "\n" if detected_newline is None else detected_newline,
                "written": False,
                "summary": _make_summary(
                    preview=preview,
                    match_count=match_count,
                    blocked=True,
                    reason=f"match_count {match_count} > confirm_over {confirm_over}",
                ),
                "match_hits": match_hits,
            }
            if return_hashes:
                result["sha256_before"] = before_sha
                result["sha256_after"] = after_sha
            return result

        written = False
        backup_path: str | None = None
        if not preview and changed:
            backup_path = make_backup_before_overwrite(path)
            _write_text_robust(path, replaced, encoding_used, detected_newline)
            written = True
            after_sha = _sha256_file(path)

        result: Dict[str, Any] = {
            "ok": True,
            "path": path,
            "action": action_norm,
            "mode": mode,
            "occurrence": occurrence,
            "line_no": line_no,
            "match_count": match_count,
            "replaced_count": replaced_count,
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
        if return_hashes:
            result["sha256_before"] = before_sha
            result["sha256_after"] = after_sha
        return result

    try:
        path = str(args.get("path") or "")
        action = str(args.get("action") or "replace")
        mode = str(args.get("mode") or "literal")
        pattern = str(args.get("pattern") or "")
        replacement = str(args.get("replacement") or "")
        preview_raw = args.get("preview", True)
        occurrence_raw = args.get("occurrence", 0)
        confirm_over = args.get("confirm_over", 10)
        encoding = str(args.get("encoding") or "utf-8")
        expand_newline_tokens_raw = args.get("expand_newline_tokens", True)
        return_hashes_raw = args.get("return_hashes", False)
        line_no_raw = args.get("line_no", 0)
        name_pattern = str(args.get("name_pattern") or "*")
        recursive_raw = args.get("recursive", True)

        valid_actions = {
            "replace",
            "append",
            "insert_at_end",
            "insert_before",
            "insert_after",
            "insert_at_line",
            "replace_all_in_files",
        }
        if action not in valid_actions:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_action",
                        default=f"[replace_in_file error] invalid action: {action}",
                    ).format(action=action),
                },
                ensure_ascii=False,
            )

        if mode not in {"literal", "regex"}:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_mode",
                        default=f"[replace_in_file error] invalid mode: {mode}",
                    ).format(mode=mode),
                },
                ensure_ascii=False,
            )

        if not isinstance(preview_raw, bool):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.preview_not_bool",
                        default="[replace_in_file error] preview must be a boolean",
                    ),
                },
                ensure_ascii=False,
            )
        preview = preview_raw

        if not isinstance(expand_newline_tokens_raw, bool):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.expand_newline_tokens_not_bool",
                        default="[replace_in_file error] expand_newline_tokens must be a boolean",
                    ),
                },
                ensure_ascii=False,
            )
        expand_newline_tokens = expand_newline_tokens_raw

        if not isinstance(return_hashes_raw, bool):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.return_hashes_not_bool",
                        default="[replace_in_file error] return_hashes must be a boolean",
                    ),
                },
                ensure_ascii=False,
            )
        return_hashes = return_hashes_raw

        if not isinstance(recursive_raw, bool):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.recursive_not_bool",
                        default="[replace_in_file error] recursive must be a boolean",
                    ),
                },
                ensure_ascii=False,
            )
        recursive = recursive_raw

        try:
            occurrence = int(occurrence_raw)
            if occurrence < 0:
                raise ValueError("occurrence must be >= 0")
        except (TypeError, ValueError) as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"[replace_in_file error] invalid occurrence: {e}",
                },
                ensure_ascii=False,
            )

        try:
            confirm_over = int(confirm_over)
            if confirm_over < 1:
                raise ValueError("confirm_over must be >= 1")
        except (TypeError, ValueError) as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"[replace_in_file error] invalid numeric argument: {e}",
                },
                ensure_ascii=False,
            )

        try:
            line_no = int(line_no_raw)
        except (TypeError, ValueError) as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"[replace_in_file error] invalid line_no: {e}",
                },
                ensure_ascii=False,
            )

        if not path:
            return json.dumps(
                {"ok": False, "error": "[replace_in_file error] path is not specified"},
                ensure_ascii=False,
            )

        if action == "replace_all_in_files":
            root_path = ensure_within_workdir(path)
            root = Path(root_path)
            if not root.exists():
                return json.dumps(
                    {"ok": False, "error": f"[replace_in_file error] path not found: {path}"},
                    ensure_ascii=False,
                )

            if root.is_file():
                targets = [root]
            else:
                pattern_glob = name_pattern or "*"
                iterator = root.rglob(pattern_glob) if recursive else root.glob(pattern_glob)
                targets = [p for p in iterator if p.is_file() and not _is_probably_binary(str(p))]

            results: List[Dict[str, Any]] = []
            changed_files = 0
            written_files = 0
            total_match_count = 0
            total_replaced_count = 0
            for fp in targets:
                try:
                    one = _single_file_edit(
                        path=str(fp),
                        action="replace",
                        mode=mode,
                        pattern=pattern,
                        replacement=replacement,
                        preview=preview,
                        occurrence=occurrence,
                        confirm_over=confirm_over,
                        encoding=encoding,
                        expand_newline_tokens=expand_newline_tokens,
                        return_hashes=return_hashes,
                        line_no=line_no,
                    )
                except Exception as e:
                    results.append(
                        {
                            "ok": False,
                            "path": str(fp),
                            "error": f"[replace_in_file error] {type(e).__name__}: {e}",
                        }
                    )
                    continue

                item = {
                    "ok": True,
                    "path": one.get("path"),
                    "changed": one.get("changed"),
                    "match_count": one.get("match_count"),
                    "replaced_count": one.get("replaced_count"),
                    "written": one.get("written"),
                    "backup": one.get("backup"),
                }
                if return_hashes:
                    item["sha256_before"] = one.get("sha256_before")
                    item["sha256_after"] = one.get("sha256_after")
                results.append(item)
                total_match_count += int(one.get("match_count") or 0)
                total_replaced_count += int(one.get("replaced_count") or 0)
                if one.get("changed"):
                    changed_files += 1
                if one.get("written"):
                    written_files += 1

            return json.dumps(
                {
                    "ok": True,
                    "action": action,
                    "path": path,
                    "name_pattern": name_pattern,
                    "recursive": recursive,
                    "scanned_files": len(targets),
                    "changed_files": changed_files,
                    "written_files": written_files,
                    "match_count": total_match_count,
                    "replaced_count": total_replaced_count,
                    "preview": preview,
                    "results": results,
                    "summary": f"{changed_files} file(s) changed",
                },
                ensure_ascii=False,
            )

        # Single-file actions
        if action != "replace_all_in_files" and not path:
            return json.dumps(
                {"ok": False, "error": "[replace_in_file error] path is not specified"},
                ensure_ascii=False,
            )

        if action in {"replace", "insert_before", "insert_after"} and pattern == "":
            return json.dumps(
                {"ok": False, "error": "[replace_in_file error] pattern must not be empty"},
                ensure_ascii=False,
            )

        if action == "insert_at_line" and line_no < 1:
            return json.dumps(
                {"ok": False, "error": "[replace_in_file error] line_no must be >= 1"},
                ensure_ascii=False,
            )

        if action in {"append", "insert_at_end"}:
            # pattern is optional for append/end, but keep the runtime behavior explicit.
            pattern = pattern or ""

        result = _single_file_edit(
            path=path,
            action=action,
            mode=mode,
            pattern=pattern,
            replacement=replacement,
            preview=preview,
            occurrence=occurrence,
            confirm_over=confirm_over,
            encoding=encoding,
            expand_newline_tokens=expand_newline_tokens,
            return_hashes=return_hashes,
            line_no=line_no,
        )
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
