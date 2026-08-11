"""replace_in_file_tool

Safely performs literal or regular-expression replacements on an existing text file.
"""

from __future__ import annotations

import codecs
import difflib
import fnmatch
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import context
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, make_backup_before_overwrite

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:replace_in_file"


def _make_summary(
    *,
    preview: bool,
    match_count: int | None = None,
    blocked: bool = False,
    reason: str | None = None,
    error: str | None = None,
    hint: str | None = None,
) -> str:
    if error is not None:
        return _("summary.error", default="Error: {error}").format(error=error)

    mc = 0 if match_count is None else int(match_count)
    if blocked:
        if reason:
            return _("summary.blocked_reason", default="Blocked: {reason}").format(
                reason=reason
            )
        return _("summary.blocked", default="Blocked: {count}").format(count=mc)

    if preview:
        msg = (
            _(
                "summary.preview_matches", default="Preview: {count} matches found"
            ).format(count=mc)
            if mc
            else _(
                "summary.preview_no_change", default="Preview: no matches (0 matches)"
            )
        )
    else:
        msg = (
            _("summary.no_change", default="Successfully no change (0 matches)")
            if mc == 0
            else _("summary.matches", default="{count} match(es)").format(count=mc)
        )

    if mc == 0 and hint:
        msg += f"\n\n[HINT] {hint}"
    return msg


TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "function": {
        "name": "replace_in_file",
        "description": _(
            "tool.description",
            default=(
                "Safely edit one text file or multiple files selected by glob. Supports literal/regex replacement, "
                "insert, append, and replace_all_in_files for the same change across a file set. "
                "Preview broad replacements before applying them. Supports backslash escapes in patterns."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "replace_in_file",
                "replace in file",
                "file replace",
                "file edit",
                "file replacement",
                "file editing",
                "text replace",
                "text edit",
                "text replacement",
                "text editing",
                "find replace",
                "search replace",
                "replace multiple files",
                "bulk replace",
                "batch edit",
                "glob replace",
                "replace all files",
                "複数ファイル置換",
                "一括置換",
                "glob置換",
            ],
        ),
        "x_search_terms_en": [
            "replace_in_file",
            "replace in file",
            "file replace",
            "file edit",
            "file replacement",
            "file editing",
            "text replace",
            "text edit",
            "text replacement",
            "text editing",
            "find replace",
            "search replace",
            "replace multiple files",
            "bulk replace",
            "batch edit",
            "glob replace",
            "replace all files",
            "replace_all_in_files",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "expand_newline_tokens": {
                    "type": "boolean",
                    "description": _(
                        "param.expand_newline_tokens.description",
                        default="Convert backslash-n/r escapes (default: true).",
                    ),
                    "default": True,
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="File path (under workdir).",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["literal", "regex"],
                    "description": _(
                        "param.mode.description",
                        default="Mode: literal or regex (for pattern/anchor_before).",
                    ),
                    "default": "literal",
                },
                "mode_after": {
                    "type": "string",
                    "enum": ["literal", "regex"],
                    "description": _(
                        "param.mode_after.description",
                        default="Mode for anchor_after (defaults to mode value).",
                    ),
                },
                "pattern": {
                    "type": "string",
                    "description": _(
                        "param.pattern.description",
                        default="Search pattern (use \\n for newlines).",
                    ),
                },
                "replacement": {
                    "type": "string",
                    "description": _(
                        "param.replacement.description", default="Replacement text."
                    ),
                },
                "po_msgid": {
                    "type": "string",
                    "description": _(
                        "param.po_msgid.description",
                        default="gettext msgid (fallback: pattern).",
                    ),
                },
                "anchor_before": {
                    "type": "string",
                    "description": _(
                        "param.anchor_before.description",
                        default="Anchor text. For insert_before: text to search and insert before that line. For replace_between: start boundary.",
                    ),
                },
                "anchor_after": {
                    "type": "string",
                    "description": _(
                        "param.anchor_after.description",
                        default="Anchor text. For insert_after: text to search and insert after that line. For replace_between: end boundary.",
                    ),
                },
                "preview": {
                    "type": "boolean",
                    "description": _(
                        "param.preview.description",
                        default="Preview only (no changes).",
                    ),
                    "default": True,
                },
                "occurrence": {
                    "type": "integer",
                    "description": _(
                        "param.occurrence.description",
                        default="Occurrence (1-based; 0 = all).",
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
                        default="Include sha256 before/after.",
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
                        "replace_between",
                        "replace_po_entry",
                        "replace_all_in_files",
                    ],
                    "description": _(
                        "param.action.description",
                        default="Action: replace/append/insert/etc.",
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
                "glob": {
                    "type": "string",
                    "description": _(
                        "param.glob.description",
                        default="Glob pattern used by replace_all_in_files (default: '*').",
                    ),
                    "default": "*",
                },
                "recur": {
                    "type": "boolean",
                    "description": _(
                        "param.recur.description",
                        default="Recursively scan under the target directory.",
                    ),
                    "default": True,
                },
            },
            "required": ["path", "replacement"],
        },
    },
}


def _read_text_robust(path: str, encoding: str, max_bytes: int) -> tuple[str, Any, str]:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(
            _(
                "err.file_too_large",
                default="File too large: {size} > {max_bytes} bytes",
            ).format(size=size, max_bytes=max_bytes)
        )

    def try_read(enc: str, errors: str) -> tuple[str, Any, str]:
        with open(path, "r", encoding=enc, errors=errors, newline=None) as f:
            content = f.read()
            return content, f.newlines, enc

    try:
        codecs.lookup(encoding)
    except LookupError as e:
        raise ValueError(
            _("err.unknown_encoding", default="Unknown encoding: {encoding}").format(
                encoding=encoding
            )
        ) from e

    # Try the validated encoding first, then UTF-8 for decode failures.
    # Japanese encodings are tried only when explicitly specified by the user,
    # because cp932/shift_jis/euc-jp can misinterpret arbitrary byte sequences
    # without raising an error (no reliable auto-detection).
    candidates = [encoding, "utf-8"]
    seen: set[str] = set()
    for enc in candidates:
        if enc in seen:
            continue
        seen.add(enc)
        try:
            return try_read(enc, "strict")
        except UnicodeDecodeError:
            continue
    return try_read("utf-8", "replace")


MAX_DIFF_INPUT_CHARS = 1_000_000
MAX_DIFF_OUTPUT_CHARS = 50_000
MAX_DIFF_OUTPUT_LINES = 400
MAX_MATCH_HITS_DETAIL = 100


def _unified_diff(path: str, original: str, replaced: str) -> str:
    if original == replaced:
        return ""
    if len(original) + len(replaced) > MAX_DIFF_INPUT_CHARS:
        return (
            "[diff omitted: input too large "
            f"({len(original)} -> {len(replaced)} chars)]"
        )
    a = original.splitlines(True)
    b = replaced.splitlines(True)
    out: list[str] = []
    out_len = 0
    out_lines = 0
    truncated = False
    for line in difflib.unified_diff(a, b, fromfile=f"a/{path}", tofile=f"b/{path}"):
        line_len = len(line)
        if (
            out_lines >= MAX_DIFF_OUTPUT_LINES
            or out_len + line_len > MAX_DIFF_OUTPUT_CHARS
        ):
            truncated = True
            break
        out.append(line)
        out_len += line_len
        out_lines += 1
    if truncated:
        out.append("\n[diff truncated: output too large]")
    return "".join(out)


def _write_text_robust(path: str, text: str, encoding: str) -> None:
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)


def _is_probably_binary(path: str) -> bool:
    """Return True for files that should not be edited as text."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return True
    if b"\x00" in head:
        return True
    if not head:
        return False
    control_count = sum(1 for byte in head if byte < 32 and byte not in (9, 10, 13))
    return control_count / len(head) > 0.10


def _expand_newline_tokens_to_lf(s: str) -> str:
    """Expand recognized backslash tokens without reinterpreting escaped slashes.

    A left-to-right scan handles ``\\\\n`` as a literal ``\\n`` rather than
    converting the second slash plus ``n`` into an actual newline.
    """
    out: list[str] = []
    i = 0
    while i < len(s):
        if s.startswith("\\r\\n", i):
            out.append("\n")
            i += 4
        elif s.startswith("\\r", i):
            out.append("\n")
            i += 2
        elif s.startswith("\\n", i):
            out.append("\n")
            i += 2
        elif s.startswith("\\t", i):
            out.append("\t")
            i += 2
        elif s.startswith("\\\\", i):
            out.append("\\")
            i += 2
        else:
            out.append(s[i])
            i += 1

    return "".join(out).replace("\r\n", "\n").replace("\r", "\n")


def _normalize_replacement_newlines(text: str, newline: Any) -> str:
    if isinstance(newline, tuple):
        if "\r\n" in newline:
            target = "\r\n"
        elif "\r" in newline:
            target = "\r"
        else:
            target = "\n"
    else:
        target = newline or "\n"
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if target != "\n":
        text = text.replace("\n", target)
    return text


def _normalize_lf(text: str) -> str:
    if "\r" not in text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass
class _Hit:
    start: int
    end: int


def _map_idx_to_line_col(text: str, idx: int) -> tuple[int, int]:
    line_no = text.count("\n", 0, idx) + 1
    last_nl = text.rfind("\n", 0, idx)
    col = idx if last_nl < 0 else idx - last_nl - 1
    return line_no, col


def _extract_same_line_context(text: str, start: int, end: int) -> tuple[str, str, str]:
    l_start = text.rfind("\n", 0, start)
    l_start = 0 if l_start < 0 else l_start + 1
    l_end = text.find("\n", end)
    l_end = len(text) if l_end < 0 else l_end
    return text[l_start:start], text[start:end], text[end:l_end]


def _find_hits_literal(
    haystack: str, needle: str, limit: int | None = None
) -> list[_Hit]:
    hits: list[_Hit] = []
    start = 0
    if not needle:
        return hits
    while True:
        pos = haystack.find(needle, start)
        if pos < 0:
            break
        hits.append(_Hit(pos, pos + len(needle)))
        if limit is not None and len(hits) >= limit:
            break
        start = pos + len(needle)
    return hits


def _nth_literal_match(haystack: str, needle: str, occurrence: int) -> _Hit | None:
    if occurrence <= 0 or not needle:
        return None
    start = 0
    for idx in range(1, occurrence + 1):
        pos = haystack.find(needle, start)
        if pos < 0:
            return None
        if idx == occurrence:
            return _Hit(pos, pos + len(needle))
        start = pos + len(needle)
    return None


def _find_hits_regex(haystack: str, pattern: re.Pattern[str]) -> list[_Hit]:
    return [_Hit(m.start(), m.end()) for m in pattern.finditer(haystack)]


def _nth_regex_match(
    haystack: str, pattern: re.Pattern[str], occurrence: int
) -> re.Match[str] | None:
    if occurrence <= 0:
        return None
    for idx, match in enumerate(pattern.finditer(haystack), start=1):
        if idx == occurrence:
            return match
    return None


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_best_fuzzy_match(text: str, pattern: str) -> dict[str, Any] | None:
    """Find the closest matching location for pattern in text when exact match fails.

    Returns a dict with position, similarity, and context, or None.
    """
    if not pattern or not text:
        return None

    text_lower = text.lower()
    pattern_lower = pattern.lower()

    # Try exact match first (case-insensitive)
    pos = text_lower.find(pattern_lower)
    if pos >= 0:
        return {
            "position": pos,
            "similarity": 1.0,
            "exact": True,
            "before_context": text[max(0, pos - 30) : pos],
            "matched_part": text[pos : pos + len(pattern)],
            "after_context": text[pos + len(pattern) : pos + len(pattern) + 30],
        }

    if len(pattern) < 5:
        return None

    matcher = difflib.SequenceMatcher(None, text_lower, pattern_lower)
    match = matcher.find_longest_match(0, len(text), 0, len(pattern))
    if match.size >= max(5, len(pattern) // 3):
        pos = match.a
        similarity = match.size / len(pattern)
        return {
            "position": pos,
            "similarity": round(similarity, 3),
            "exact": False,
            "before_context": text[max(0, pos - 30) : pos],
            "matched_part": text[pos : pos + match.size],
            "after_context": text[pos + match.size : pos + match.size + 30],
        }

    return None


def _get_failure_hint(original: str, pattern: str, mode: str) -> str | None:
    if not pattern:
        return None
    p_strip = pattern.strip()
    if p_strip and p_strip != pattern and p_strip in original:
        return _(
            "hint.indentation_mismatch",
            default="Pattern not found, but it exists if leading/trailing whitespace is ignored. Check your indentation.",
        )
    if mode == "literal" and any(c in pattern for c in ".*+?^$[]{}()|"):
        return _(
            "hint.possible_regex",
            default="Pattern looks like it contains regex-style meta-characters but 'mode' is 'literal'.",
        )
    fuzzy = _find_best_fuzzy_match(original, pattern)
    if fuzzy and not fuzzy.get("exact"):
        sim = fuzzy.get("similarity", 0)
        matched = fuzzy.get("matched_part", "")
        before = fuzzy.get("before_context", "")
        after = fuzzy.get("after_context", "")
        if sim >= 0.5:
            return _(
                "hint.fuzzy_match",
                default=(
                    "No exact match found, but {sim:.0%} similar content found near "
                    "position {pos}: ...{before}[{matched}]{after}... "
                    "Check whitespace, indentation, or special characters."
                ),
            ).format(
                sim=sim,
                pos=fuzzy.get("position", 0),
                before=before[-20:],
                matched=matched[:40],
                after=after[:20],
            )
    return _(
        "hint.check_exact",
        default="No matches. Use 'search_files' or 'read_file' to copy the exact content including spaces.",
    )


def _newline_name(newline: str) -> str:
    if newline == "\r\n":
        return "CRLF"
    if newline == "\r":
        return "CR"
    if newline == "\n":
        return "LF"
    return "UNKNOWN"


def _newline_profile(newline: Any) -> str:
    if isinstance(newline, tuple):
        names = [_newline_name(nl) for nl in newline]
        if len(names) > 1:
            return "MIXED(" + ",".join(names) + ")"
        return names[0] if names else "UNKNOWN"
    if newline is None:
        return "NONE"
    return _newline_name(str(newline))


def _newline_details(newline: Any, selected_style: str) -> dict[str, Any]:
    if isinstance(newline, tuple):
        detected = list(newline)
    elif newline is None:
        detected = []
    else:
        detected = [newline]
    return {
        "profile": _newline_profile(newline),
        "detected": [_newline_name(str(nl)) for nl in detected],
        "mixed": isinstance(newline, tuple) and len(newline) > 1,
        "selected_for_write": _newline_name(selected_style),
    }


def _text_newline_flags(text: str) -> dict[str, Any]:
    return {
        "contains_actual_newline": "\n" in text or "\r" in text,
        "contains_escaped_newline_tokens": "\\n" in text or "\\r" in text,
        "repr": repr(text),
    }


def _diagnostics_hint(diagnostics: dict[str, Any] | None) -> str | None:
    if not diagnostics:
        return None
    hints = diagnostics.get("hints")
    if not isinstance(hints, list) or not hints:
        return None
    return str(hints[0])


def _po_unescape_token(token: str) -> str:
    t = (token or "").strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]

    out: list[str] = []
    i = 0
    while i < len(t):
        ch = t[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(t):
            out.append("\\")
            break

        esc = t[i]
        i += 1
        if esc == "n":
            out.append("\n")
        elif esc == "t":
            out.append("\t")
        elif esc == "r":
            out.append("\r")
        elif esc == "\\":
            out.append("\\")
        elif esc == '"':
            out.append('"')
        else:
            out.append("\\" + esc)

    return "".join(out)


def _po_escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def _po_encode_msgstr(text: str) -> list[str]:
    normalized = _normalize_lf(text)
    if normalized == "":
        return ['msgstr ""\n']
    if "\n" not in normalized and "\r" not in normalized:
        return [f'msgstr "{_po_escape_text(normalized)}"\n']

    out = ['msgstr ""\n']
    for part in normalized.splitlines(keepends=True):
        out.append(f'"{_po_escape_text(part)}"\n')
    return out


def _po_parse_entry_block(block_lines: list[str]) -> dict[str, Any] | None:
    if not block_lines:
        return None
    if not block_lines[0].lstrip().startswith("msgid "):
        return None

    def collect(start_idx: int, prefix: str) -> tuple[str, int]:
        token = block_lines[start_idx].lstrip()[len(prefix) :].strip()
        parts = [_po_unescape_token(token)]
        i = start_idx + 1
        while i < len(block_lines):
            cont = block_lines[i].strip()
            if len(cont) >= 2 and cont[0] == '"' and cont[-1] == '"':
                parts.append(_po_unescape_token(cont))
                i += 1
            else:
                break
        return "".join(parts), i

    msgid, msgid_end = collect(0, "msgid ")
    if msgid_end >= len(block_lines) or not block_lines[msgid_end].lstrip().startswith(
        "msgstr "
    ):
        return None
    msgstr_start = msgid_end
    msgstr, msgstr_end = collect(msgstr_start, "msgstr ")
    msgstr_line_count = max(1, msgstr_end - msgstr_start)
    msgstr_is_empty = msgstr == ""
    if msgstr_is_empty:
        msgstr_kind = "empty"
    elif msgstr_line_count > 1:
        msgstr_kind = "multiline"
    else:
        msgstr_kind = "singleline"
    return {
        "msgid": msgid,
        "msgstr": msgstr,
        "msgstr_start": msgstr_start,
        "msgstr_end": msgstr_end,
        "msgstr_line_count": msgstr_line_count,
        "msgstr_is_empty": msgstr_is_empty,
        "msgstr_kind": msgstr_kind,
    }


def _build_no_match_diagnostics(
    *,
    original: str,
    search_text: str,
    mode: str,
    action: str,
    expand_newline_tokens: bool,
    newline_info: dict[str, Any] | None = None,
    anchor_before: str = "",
    anchor_after: str = "",
    po_msgid: str = "",
) -> dict[str, Any]:
    search_flags = _text_newline_flags(search_text)
    diagnostics: dict[str, Any] = {
        "action": action,
        "mode": mode,
        "newline": newline_info or {},
        "expand_newline_tokens": expand_newline_tokens,
        "search_text_length": len(search_text),
        "search_text_flags": search_flags,
        "contains_escaped_newline_tokens": search_flags[
            "contains_escaped_newline_tokens"
        ],
        "contains_actual_newline": search_flags["contains_actual_newline"],
        "contains_regex_meta": bool(re.search(r"[.*+?^$\[\]{}()|]", search_text)),
    }

    hints: list[str] = []
    stripped = search_text.strip()

    # Fuzzy match hint first (highest priority diagnostic)
    if action in ("replace", "insert_before", "insert_after") and search_text:
        fuzzy = _find_best_fuzzy_match(original, search_text)
        if fuzzy and not fuzzy.get("exact") and fuzzy.get("similarity", 0) >= 0.5:
            sim = fuzzy.get("similarity", 0)
            matched = fuzzy.get("matched_part", "")
            before = fuzzy.get("before_context", "")
            after = fuzzy.get("after_context", "")
            hints.append(
                _(
                    "hint.fuzzy_match",
                    default=(
                        "No exact match found, but {sim:.0%} similar content near "
                        "position {pos}: ...{before}[{matched}]{after}... "
                        "Check whitespace, indentation, or special characters."
                    ),
                ).format(
                    sim=sim,
                    pos=fuzzy.get("position", 0),
                    before=before[-20:],
                    matched=matched[:40],
                    after=after[:20],
                )
            )

    if not expand_newline_tokens and diagnostics["contains_escaped_newline_tokens"]:
        hints.append(
            _(
                "hint.escaped_newline_tokens_not_expanded",
                default=(
                    "Escaped newline tokens were not expanded. Set "
                    "expand_newline_tokens=true or use actual newlines."
                ),
            )
        )
    if mode == "literal" and diagnostics["contains_regex_meta"]:
        hints.append(
            _(
                "hint.possible_regex_mode_literal",
                default=(
                    "Pattern looks like it contains regex-style meta-characters "
                    "but mode is literal."
                ),
            )
        )
    if stripped and stripped != search_text and stripped in original:
        hints.append(
            _(
                "hint.indentation_mismatch",
                default=(
                    "Pattern not found, but it exists if leading/trailing "
                    "whitespace is ignored. Check your indentation."
                ),
            )
        )
    if diagnostics["newline"].get("mixed"):
        hints.append(
            _(
                "hint.mixed_newline_write_style",
                default=(
                    "Input file has mixed newline styles. Writing will use the "
                    "selected_for_write style."
                ),
            )
        )

    if action in ("replace_between", "insert_before", "insert_after"):
        if anchor_before:
            diagnostics["anchor_before"] = anchor_before
            diagnostics["anchor_before_flags"] = _text_newline_flags(anchor_before)
            diagnostics["anchor_before_found"] = bool(
                anchor_before and anchor_before in original
            )
            if anchor_before and not diagnostics["anchor_before_found"]:
                hints.append(
                    _(
                        "hint.anchor_before_not_found",
                        default="anchor_before was not found.",
                    )
                )
        if anchor_after:
            diagnostics["anchor_after"] = anchor_after
            diagnostics["anchor_after_flags"] = _text_newline_flags(anchor_after)
            diagnostics["anchor_after_found"] = bool(
                anchor_after and anchor_after in original
            )
            if anchor_after and not diagnostics["anchor_after_found"]:
                hints.append(
                    _(
                        "hint.anchor_after_not_found",
                        default="anchor_after was not found.",
                    )
                )
    elif action == "replace_po_entry":
        target = po_msgid or search_text
        diagnostics["po_msgid"] = target
        diagnostics["po_msgid_flags"] = _text_newline_flags(target)
        diagnostics["po_msgid_found"] = bool(target and target in original)
        if not diagnostics["po_msgid_found"]:
            hints.append(
                _(
                    "hint.po_msgid_not_found",
                    default="msgid was not found in the .po file.",
                )
            )

    if not hints:
        hints.append(
            _(
                "hint.check_exact",
                default=(
                    "No matches. Use 'search_files' or 'read_file' to copy the "
                    "exact content including spaces."
                ),
            )
        )

    diagnostics["hints"] = hints
    return diagnostics


def _replace_po_entry_text(
    original: str,
    target_msgid: str,
    replacement: str,
    occurrence: int,
    *,
    expand_newline_tokens: bool,
    newline_info: dict[str, Any],
) -> tuple[str, int, int, list[dict[str, Any]], dict[str, Any] | None]:
    lines = original.splitlines(keepends=True)
    out: list[str] = []
    match_hits: list[dict[str, Any]] = []
    match_total = 0
    replaced_total = 0
    msgstr_is_empty_any = False
    msgstr_kinds_seen: set[str] = set()
    msgstr_line_counts_seen: set[int] = set()
    i = 0

    while i < len(lines):
        if not lines[i].lstrip().startswith("msgid "):
            out.append(lines[i])
            i += 1
            continue

        j = i + 1
        while j < len(lines) and not lines[j].lstrip().startswith("msgid "):
            j += 1

        block = lines[i:j]
        parsed = _po_parse_entry_block(block)
        if parsed and parsed["msgid"] == target_msgid:
            match_total += 1
            msgstr_is_empty_any = msgstr_is_empty_any or bool(parsed["msgstr_is_empty"])
            msgstr_kinds_seen.add(str(parsed["msgstr_kind"]))
            msgstr_line_counts_seen.add(int(parsed["msgstr_line_count"]))
            if len(match_hits) < MAX_MATCH_HITS_DETAIL:
                match_hits.append(
                    {
                        "line_no": i + 1,
                        "col": 0,
                        "msgid": parsed["msgid"],
                        "msgstr_before": parsed["msgstr"][:200],
                        "msgstr_line_count": parsed["msgstr_line_count"],
                        "msgstr_is_empty": parsed["msgstr_is_empty"],
                        "msgstr_kind": parsed["msgstr_kind"],
                        "entry_kind": "po",
                    }
                )
            should_replace = occurrence == 0 or occurrence == match_total
            if should_replace:
                out.extend(block[: parsed["msgstr_start"]])
                out.extend(_po_encode_msgstr(replacement))
                out.extend(block[parsed["msgstr_end"] :])
                replaced_total += 1
            else:
                out.extend(block)
        else:
            out.extend(block)
        i = j

    if match_total == 0:
        return (
            original,
            0,
            0,
            [],
            _build_no_match_diagnostics(
                original=original,
                search_text=target_msgid,
                mode="literal",
                action="replace_po_entry",
                expand_newline_tokens=expand_newline_tokens,
                newline_info=newline_info,
                po_msgid=target_msgid,
            ),
        )

    if occurrence > 0 and occurrence > match_total:
        diag = _build_no_match_diagnostics(
            original=original,
            search_text=target_msgid,
            mode="literal",
            action="replace_po_entry",
            expand_newline_tokens=expand_newline_tokens,
            newline_info=newline_info,
            po_msgid=target_msgid,
        )
        diag["po_msgid_found"] = True
        diag["po_msgid_match_count"] = match_total
        diag["po_msgid_replaced_count"] = 0
        diag["msgstr_is_empty"] = msgstr_is_empty_any
        diag["msgstr_kinds"] = sorted(msgstr_kinds_seen)
        diag["msgstr_line_counts"] = sorted(msgstr_line_counts_seen)
        if len(diag["msgstr_kinds"]) == 1:
            diag["msgstr_kind"] = diag["msgstr_kinds"][0]
        if len(diag["msgstr_line_counts"]) == 1:
            diag["msgstr_line_count"] = diag["msgstr_line_counts"][0]
        diag["hints"] = [
            _(
                "hint.occurrence_exceeds_matches",
                default=(
                    "Requested occurrence {occurrence} exceeds available "
                    "matches ({match_count})."
                ),
            ).format(occurrence=occurrence, match_count=match_total),
            *diag["hints"],
        ]
        return original, match_total, 0, match_hits, diag

    diag = {
        "po_msgid": target_msgid,
        "po_msgid_found": True,
        "po_msgid_match_count": match_total,
        "po_msgid_replaced_count": replaced_total,
        "msgstr_is_empty": msgstr_is_empty_any,
        "msgstr_kinds": sorted(msgstr_kinds_seen),
        "msgstr_line_counts": sorted(msgstr_line_counts_seen),
    }
    if len(diag["msgstr_kinds"]) == 1:
        diag["msgstr_kind"] = diag["msgstr_kinds"][0]
    if len(diag["msgstr_line_counts"]) == 1:
        diag["msgstr_line_count"] = diag["msgstr_line_counts"][0]

    return "".join(out), match_total, replaced_total, match_hits, diag


def _replace_between_text(
    original: str,
    anchor_before: str,
    anchor_after: str,
    replacement: str,
    mode: str,
    occurrence: int,
    *,
    expand_newline_tokens: bool,
    newline_info: dict[str, Any],
    mode_after: str | None = None,
) -> tuple[str, int, int, list[dict[str, Any]], dict[str, Any] | None]:
    mode_b = mode
    mode_a = mode_after if mode_after is not None else mode
    before_pattern = re.compile(anchor_before) if mode_b == "regex" else None
    before_hits = (
        _find_hits_regex(original, before_pattern)
        if before_pattern is not None
        else _find_hits_literal(original, anchor_before)
    )

    def _no_match_diag(search_text: str) -> dict[str, Any]:
        return _build_no_match_diagnostics(
            original=original,
            search_text=search_text,
            mode=mode_b if search_text == anchor_before else mode_a,
            action="replace_between",
            expand_newline_tokens=expand_newline_tokens,
            newline_info=newline_info,
            anchor_before=anchor_before,
            anchor_after=anchor_after,
        )

    if not before_hits:
        return original, 0, 0, [], _no_match_diag(anchor_before)

    after_pattern = re.compile(anchor_after) if mode_a == "regex" else None
    after_hits = (
        _find_hits_regex(original, after_pattern)
        if after_pattern is not None
        else _find_hits_literal(original, anchor_after)
    )

    def _occurrence_diag() -> dict[str, Any]:
        diag = _no_match_diag(anchor_before)
        diag["hints"] = [
            _(
                "hint.occurrence_exceeds_matches",
                default=(
                    "Requested occurrence {occurrence} exceeds available "
                    "matches ({match_count})."
                ),
            ).format(occurrence=occurrence, match_count=len(before_hits)),
            *diag["hints"],
        ]
        return diag

    def _after_missing_diag() -> dict[str, Any]:
        diag = _no_match_diag(anchor_after)
        diag["hints"] = [
            _(
                "hint.anchor_after_not_found_after_before",
                default="anchor_after was not found after anchor_before.",
            ),
            *diag["hints"],
        ]
        return diag

    if occurrence > 0:
        if occurrence > len(before_hits):
            return original, len(before_hits), 0, [], _occurrence_diag()
        selected_before = before_hits[occurrence - 1]
        selected_after = next(
            (hit for hit in after_hits if hit.start >= selected_before.end),
            None,
        )
        if selected_after is None:
            return original, len(before_hits), 0, [], _after_missing_diag()
        pairs = [(selected_before, selected_after)]
    else:
        pairs: list[tuple[_Hit, _Hit]] = []
        after_index = 0
        for before_hit in before_hits:
            while (
                after_index < len(after_hits)
                and after_hits[after_index].start < before_hit.end
            ):
                after_index += 1
            if after_index >= len(after_hits):
                break
            pairs.append((before_hit, after_hits[after_index]))
            after_index += 1
        if not pairs:
            return original, len(before_hits), 0, [], _after_missing_diag()

    replaced_text = original
    for before_hit, after_hit in reversed(pairs):
        replaced_text = (
            replaced_text[: before_hit.end]
            + replacement
            + replaced_text[after_hit.start :]
        )

    match_hits: list[dict[str, Any]] = []
    for before_hit, after_hit in pairs[:MAX_MATCH_HITS_DETAIL]:
        lno, col = _map_idx_to_line_col(original, before_hit.start)
        match_hits.append(
            {
                "line_no": lno,
                "col": col,
                "anchor_before": anchor_before,
                "anchor_after": anchor_after,
                "block_before": original[before_hit.start : before_hit.end],
                "block_after": original[after_hit.start : after_hit.end],
            }
        )

    diagnostics = None
    if len(pairs) > MAX_MATCH_HITS_DETAIL:
        diagnostics = {
            "match_hits_truncated": True,
            "match_hits_limit": MAX_MATCH_HITS_DETAIL,
            "match_hits_omitted": len(pairs) - MAX_MATCH_HITS_DETAIL,
        }
    return replaced_text, len(pairs), len(pairs), match_hits, diagnostics


def _pick_newline_style(newline: Any) -> str:
    if isinstance(newline, tuple):
        if "\r\n" in newline:
            return "\r\n"
        if "\r" in newline:
            return "\r"
        if "\n" in newline:
            return "\n"
    return newline or "\n"


def _apply_newline_style(text: str, newline: str) -> str:
    if newline == "\n" and "\r" not in text:
        return text
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if newline == "\n":
        return text
    return text.replace("\n", newline)


def run_tool(args: dict[str, Any]) -> str:
    cb = context.get_callbacks()

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
        po_msgid: str,
        anchor_before: str,
        anchor_after: str,
        mode_after: str | None = None,
    ) -> dict[str, Any]:
        ensure_within_workdir(path)
        original, nl, enc_used = _read_text_robust(
            path, encoding, cb.read_file_max_bytes
        )
        newline_style = _pick_newline_style(nl)
        newline_info = _newline_details(nl, newline_style)
        orig_norm = _normalize_lf(original)
        before_sha = _sha256_file(path) if return_hashes else None

        p2 = _expand_newline_tokens_to_lf(pattern) if expand_newline_tokens else pattern
        r2 = (
            _expand_newline_tokens_to_lf(replacement)
            if expand_newline_tokens
            else replacement
        )
        po_target = (
            _expand_newline_tokens_to_lf(po_msgid)
            if expand_newline_tokens
            else po_msgid
        )
        anchor_before_norm = (
            _expand_newline_tokens_to_lf(anchor_before)
            if expand_newline_tokens
            else anchor_before
        )
        anchor_after_norm = (
            _expand_newline_tokens_to_lf(anchor_after)
            if expand_newline_tokens
            else anchor_after
        )

        # Determine search key: for insert_before/insert_after, anchor text takes priority over pattern.
        search_key = p2
        if action == "insert_before" and anchor_before_norm:
            search_key = anchor_before_norm
        elif action == "insert_after" and anchor_after_norm:
            search_key = anchor_after_norm

        regex_pattern = (
            re.compile(search_key, re.MULTILINE) if mode == "regex" else None
        )
        hits: list[_Hit] = []
        target_hit: _Hit | None = None
        match_count = 0
        if action in {"replace", "insert_before", "insert_after"}:
            if regex_pattern is not None:
                if occurrence == 0:
                    hits = _find_hits_regex(orig_norm, regex_pattern)
                    match_count = len(hits)
                else:
                    match_count = sum(1 for _ in regex_pattern.finditer(orig_norm))
                    target_match = _nth_regex_match(
                        orig_norm, regex_pattern, occurrence
                    )
                    if target_match is not None:
                        target_hit = _Hit(target_match.start(), target_match.end())
                        hits = [target_hit]
            else:
                if occurrence == 0:
                    hits = _find_hits_literal(orig_norm, search_key)
                    match_count = len(hits)
                else:
                    match_count = orig_norm.count(search_key) if search_key else 0
                    target_hit = _nth_literal_match(orig_norm, search_key, occurrence)
                    if target_hit is not None:
                        hits = [target_hit]

        replaced_text = orig_norm
        replaced_count = 0
        match_hits: list[dict[str, Any]] = []
        backup_path = None
        diagnostics: dict[str, Any] | None = None
        if action == "replace_po_entry":
            target = po_target or p2
            if not target:
                raise ValueError(
                    _(
                        "err.po_msgid_required",
                        default="po_msgid is required for replace_po_entry",
                    )
                )
            replaced_text, match_count, replaced_count, match_hits, diagnostics = (
                _replace_po_entry_text(
                    orig_norm,
                    target,
                    r2,
                    occurrence,
                    expand_newline_tokens=expand_newline_tokens,
                    newline_info=newline_info,
                )
            )
        elif action == "replace_between":
            if not anchor_before_norm or not anchor_after_norm:
                raise ValueError(
                    _(
                        "err.anchors_required",
                        default=(
                            "anchor_before and anchor_after are required "
                            "for replace_between"
                        ),
                    )
                )
            replaced_text, match_count, replaced_count, match_hits, diagnostics = (
                _replace_between_text(
                    orig_norm,
                    anchor_before_norm,
                    anchor_after_norm,
                    r2,
                    mode,
                    occurrence,
                    expand_newline_tokens=expand_newline_tokens,
                    newline_info=newline_info,
                    mode_after=mode_after,
                )
            )
        elif action == "replace" and match_count > 0:
            if occurrence == 0:
                if regex_pattern is not None:
                    replaced_text, replaced_count = regex_pattern.subn(r2, orig_norm)
                else:
                    replaced_text = orig_norm.replace(p2, r2)
                    replaced_count = match_count
            elif 0 < occurrence <= match_count:
                h = hits[0]
                if regex_pattern is not None:
                    m = _nth_regex_match(orig_norm, regex_pattern, occurrence)
                    if m is None:
                        raise RuntimeError(
                            "regex occurrence disappeared during replacement"
                        )
                    replaced_text = (
                        orig_norm[: h.start] + m.expand(r2) + orig_norm[h.end :]
                    )
                else:
                    replaced_text = orig_norm[: h.start] + r2 + orig_norm[h.end :]
                replaced_count = 1
            limit = MAX_MATCH_HITS_DETAIL
            truncated = len(hits) > limit
            for h in hits[:limit]:
                lno, col = _map_idx_to_line_col(orig_norm, h.start)
                bef, mat, aft = _extract_same_line_context(orig_norm, h.start, h.end)
                match_hits.append(
                    {
                        "line_no": lno,
                        "col": col,
                        "match_text": mat,
                        "before": bef[-200:],
                        "after": aft[:200],
                    }
                )
            if truncated:
                if diagnostics is None:
                    diagnostics = {}
                diagnostics["match_hits_truncated"] = True
                diagnostics["match_hits_limit"] = limit
                diagnostics["match_hits_omitted"] = len(hits) - limit

        elif action in {"insert_before", "insert_after"} and hits:
            # Insert at positions from the original text, right to left, so
            # offsets remain valid when occurrence=0 means all matches.
            for h in reversed(hits):
                if action == "insert_before":
                    idx = orig_norm.rfind("\n", 0, h.start)
                    ins_at = 0 if idx < 0 else idx + 1
                else:
                    idx = orig_norm.find("\n", h.end)
                    ins_at = len(orig_norm) if idx < 0 else idx + 1
                replaced_text = replaced_text[:ins_at] + r2 + replaced_text[ins_at:]

            replaced_count = len(hits)
            limit = MAX_MATCH_HITS_DETAIL
            for h in hits[:limit]:
                if action == "insert_before":
                    idx = orig_norm.rfind("\n", 0, h.start)
                    ins_at = 0 if idx < 0 else idx + 1
                else:
                    idx = orig_norm.find("\n", h.end)
                    ins_at = len(orig_norm) if idx < 0 else idx + 1
                lno, col = _map_idx_to_line_col(orig_norm, ins_at)
                lno_match, col_match = _map_idx_to_line_col(orig_norm, h.start)
                match_hits.append(
                    {
                        "line_no": lno,
                        "col": col,
                        "insert_action": action,
                        "match_line_no": lno_match,
                        "match_col": col_match,
                        "match_text": orig_norm[h.start : h.end],
                        "insert_text_preview": r2[:200],
                    }
                )
            if len(hits) > limit:
                if diagnostics is None:
                    diagnostics = {}
                diagnostics["match_hits_truncated"] = True
                diagnostics["match_hits_limit"] = limit
                diagnostics["match_hits_omitted"] = len(hits) - limit

        elif action == "insert_at_line":
            lines = orig_norm.splitlines(True)
            max_line = len(lines) + 1
            if line_no <= 0:
                line_no = 1  # 0 is treated as the first line
            if line_no > max_line:
                raise ValueError(
                    _(
                        "err.line_no_out_of_range",
                        default=(
                            "line_no {line_no} out of range for file with "
                            "{line_count} line(s) (valid: 1..{max_line})"
                        ),
                    ).format(
                        line_no=line_no,
                        line_count=len(lines),
                        max_line=max_line,
                    )
                )
            off = sum(len(line) for line in lines[: line_no - 1])
            replaced_text = orig_norm[:off] + r2 + orig_norm[off:]
            replaced_count = 1
            lno, col = _map_idx_to_line_col(orig_norm, off)
            match_hits = [
                {
                    "line_no": lno,
                    "col": col,
                    "insert_action": "insert_at_line",
                    "target_line": line_no,
                    "insert_text_preview": r2[:200],
                }
            ]
            match_count = replaced_count

        elif action == "insert_at_end":
            prefix = "" if (not orig_norm or orig_norm.endswith("\n")) else "\n"
            replaced_text = orig_norm + prefix + r2
            replaced_count = 1
            match_count = 1
            insert_line = orig_norm.count("\n") + (
                1 if not orig_norm or orig_norm.endswith("\n") else 2
            )
            match_hits = [
                {
                    "line_no": insert_line,
                    "col": 0,
                    "insert_action": "insert_at_end",
                    "insert_text_preview": r2[:200],
                    "added_leading_newline": bool(prefix),
                }
            ]

        hint = None
        if diagnostics is not None:
            hint = _diagnostics_hint(diagnostics)
        if (
            diagnostics is None
            and match_count == 0
            and action in {"replace", "insert_before", "insert_after"}
        ):
            diagnostics = _build_no_match_diagnostics(
                original=orig_norm,
                search_text=search_key,
                mode=mode,
                action=action,
                expand_newline_tokens=expand_newline_tokens,
                newline_info=newline_info,
                anchor_before=anchor_before_norm,
                anchor_after=anchor_after_norm,
            )
            hint = _diagnostics_hint(diagnostics)
        if (
            hint is None
            and match_count == 0
            and action in {"replace", "insert_before", "insert_after"}
        ):
            hint = _get_failure_hint(orig_norm, search_key, mode)

        changed = replaced_text != orig_norm
        if (
            not preview
            and action
            in {
                "replace",
                "replace_po_entry",
                "replace_between",
                "insert_before",
                "insert_after",
            }
            and occurrence == 0
            and match_count > confirm_over
        ):
            return {
                "ok": True,
                "path": path,
                "match_count": match_count,
                "changed": False,
                "blocked": True,
                "summary": _make_summary(
                    preview=preview,
                    match_count=match_count,
                    blocked=True,
                    reason=f"match_count {match_count} > confirm_over {confirm_over}",
                ),
            }

        written = False
        if not preview and changed:
            backup_path = make_backup_before_overwrite(path)
            _write_text_robust(
                path, _apply_newline_style(replaced_text, newline_style), enc_used
            )
            written = True

        after_sha = _sha256_file(path) if return_hashes else None
        res = {
            "ok": True,
            "path": path,
            "action": action,
            "mode": mode,
            "match_count": match_count,
            "replaced_count": replaced_count,
            "changed": changed,
            "preview": preview,
            "written": written,
            "occurrence": occurrence,
            "line_no": line_no,
            "encoding": enc_used,
            "newline": newline_info,
            "effective_pattern_flags": _text_newline_flags(p2),
            "effective_replacement_flags": _text_newline_flags(r2),
            "diff": _unified_diff(path, original, replaced_text),
            "summary": _make_summary(
                preview=preview, match_count=match_count, hint=hint
            ),
        }
        if diagnostics is not None:
            res["diagnostics"] = diagnostics
        if backup_path is not None:
            res["backup"] = backup_path
        if match_hits:
            res["match_hits"] = match_hits
        if return_hashes:
            res.update({"sha256_before": before_sha, "sha256_after": after_sha})
        return res

    try:
        path = str(args.get("path", ""))
        action = str(args.get("action", "replace"))
        mode = str(args.get("mode", "literal"))
        mode_after = str(args.get("mode_after", "")) or None
        if action == "append":
            action = "insert_at_end"
        pattern = str(args.get("pattern", ""))
        if "replacement" not in args:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.replacement_required",
                        default="replacement is required",
                    ),
                },
                ensure_ascii=False,
            )
        replacement = str(args.get("replacement", ""))
        preview = bool(args.get("preview", True))
        occurrence = int(args.get("occurrence", 0))
        confirm_over = int(args.get("confirm_over", 10))
        line_no = int(args.get("line_no", 0))
        po_msgid = str(args.get("po_msgid", args.get("msgid", "")))
        anchor_before = str(args.get("anchor_before", ""))
        anchor_after = str(args.get("anchor_after", ""))

        valid_modes = {"literal", "regex"}
        if mode not in valid_modes:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_mode",
                        default="invalid mode: {mode}",
                    ).format(mode=mode),
                },
                ensure_ascii=False,
            )
        if mode_after and mode_after not in valid_modes:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_mode_after",
                        default="invalid mode_after: {mode}",
                    ).format(mode=mode_after),
                },
                ensure_ascii=False,
            )

        valid_actions = {
            "replace",
            "append",
            "insert_at_end",
            "insert_before",
            "insert_after",
            "insert_at_line",
            "replace_between",
            "replace_po_entry",
            "replace_all_in_files",
        }
        if action not in valid_actions:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_action",
                        default="invalid action: {action}",
                    ).format(action=action),
                },
                ensure_ascii=False,
            )

        if not path:
            return json.dumps(
                {
                    "ok": False,
                    "error": _("err.path_missing", default="path is not specified"),
                },
                ensure_ascii=False,
            )

        pattern_required_actions = {
            "replace",
            "replace_all_in_files",
        }
        if action in pattern_required_actions and not pattern:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.pattern_required",
                        default="pattern is required for this action",
                    ),
                },
                ensure_ascii=False,
            )

        # For insert_before/insert_after, pattern is optional if the corresponding anchor is provided.
        if (
            action in ("insert_before", "insert_after")
            and not pattern
            and not (
                (action == "insert_before" and anchor_before)
                or (action == "insert_after" and anchor_after)
            )
        ):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.pattern_or_anchor_required",
                        default="pattern (or anchor_before/anchor_after) is required for this action",
                    ),
                },
                ensure_ascii=False,
            )

        if action == "replace_all_in_files":
            root = Path(ensure_within_workdir(path))
            exclude_dirs = {
                ".git",
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                ".uag",
                ".pytest_cache",
                ".mypy_cache",
                ".idea",
                ".vscode",
            }
            exclude_globs = {
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
            raw_exclude_globs = args.get("exclude_globs", []) or []
            if isinstance(raw_exclude_globs, str):
                exclude_globs.add(raw_exclude_globs)
            else:
                exclude_globs.update(str(g) for g in raw_exclude_globs if str(g))

            def _eligible_target(candidate: Path) -> bool:
                if not candidate.is_file() or _is_probably_binary(str(candidate)):
                    return False
                try:
                    rel = candidate.relative_to(root)
                    rel_name = "/".join(rel.parts)
                    rel_parts = rel.parts
                except ValueError:
                    rel_name = candidate.name
                    rel_parts = candidate.parts
                if any(part in exclude_dirs for part in rel_parts[:-1]):
                    return False
                return not any(
                    fnmatch.fnmatch(candidate.name, glob)
                    or fnmatch.fnmatch(rel_name, glob)
                    for glob in exclude_globs
                )

            if root.is_file():
                targets = [root] if _eligible_target(root) else []
            else:
                globber = root.rglob if bool(args.get("recur", True)) else root.glob
                name_pattern = str(args.get("glob", "*"))
                targets = [
                    candidate
                    for candidate in globber(name_pattern)
                    if _eligible_target(candidate)
                ]
            # Preflight the complete target set before a non-preview bulk
            # replacement.  Without this pass, files processed early in the
            # loop could be written before a later file pushes the aggregate
            # match count over confirm_over.
            if not preview:
                preflight_total = 0
                preflight_errors: list[dict[str, Any]] = []
                preflight_encoding = str(args.get("encoding", "utf-8"))
                preflight_expand = bool(args.get("expand_newline_tokens", True))
                preflight_pattern = (
                    _expand_newline_tokens_to_lf(pattern)
                    if preflight_expand
                    else pattern
                )
                preflight_regex = (
                    re.compile(preflight_pattern, re.MULTILINE)
                    if mode == "regex"
                    else None
                )
                for fp in targets:
                    try:
                        content, _preflight_newlines, _preflight_encoding_used = (
                            _read_text_robust(
                                str(fp), preflight_encoding, cb.read_file_max_bytes
                            )
                        )
                        content = _normalize_lf(content)
                        if preflight_regex is not None:
                            preflight_total += sum(
                                1 for _ in preflight_regex.finditer(content)
                            )
                        else:
                            preflight_total += len(
                                _find_hits_literal(content, preflight_pattern)
                            )
                    except Exception as exc:
                        preflight_errors.append(
                            {"ok": False, "path": str(fp), "error": str(exc)}
                        )
                if preflight_errors:
                    return json.dumps(
                        {
                            "ok": False,
                            "path": str(root),
                            "action": action,
                            "results": preflight_errors,
                            "scanned_files": len(targets),
                            "changed_files": 0,
                            "written_files": 0,
                            "match_count": preflight_total,
                            "replaced_count": 0,
                            "summary": _(
                                "summary.error",
                                default="Error: bulk preflight failed",
                            ),
                        },
                        ensure_ascii=False,
                    )
                if preflight_total > confirm_over:
                    return json.dumps(
                        {
                            "ok": True,
                            "path": str(root),
                            "action": action,
                            "results": [],
                            "scanned_files": len(targets),
                            "changed_files": 0,
                            "written_files": 0,
                            "match_count": preflight_total,
                            "replaced_count": 0,
                            "blocked": True,
                            "summary": _make_summary(
                                preview=False,
                                match_count=preflight_total,
                                blocked=True,
                                reason=(
                                    f"match_count {preflight_total} > "
                                    f"confirm_over {confirm_over}"
                                ),
                            ),
                        },
                        ensure_ascii=False,
                    )

            results = []
            for fp in targets:
                try:
                    results.append(
                        _single_file_edit(
                            path=str(fp),
                            action="replace",
                            mode=mode,
                            pattern=pattern,
                            replacement=replacement,
                            preview=preview,
                            occurrence=occurrence,
                            confirm_over=confirm_over,
                            encoding=str(args.get("encoding", "utf-8")),
                            expand_newline_tokens=bool(
                                args.get("expand_newline_tokens", True)
                            ),
                            return_hashes=bool(args.get("return_hashes", False)),
                            line_no=line_no,
                            po_msgid=po_msgid,
                            anchor_before=anchor_before,
                            anchor_after=anchor_after,
                            mode_after=str(args.get("mode_after", "")) or None,
                        )
                    )
                except Exception as e:
                    results.append({"ok": False, "path": str(fp), "error": str(e)})
            scanned_files = len(targets)
            changed_files = sum(1 for r in results if r.get("changed"))
            written_files = sum(1 for r in results if r.get("written"))
            match_count = sum(int(r.get("match_count", 0) or 0) for r in results)
            replaced_count = sum(int(r.get("replaced_count", 0) or 0) for r in results)
            return json.dumps(
                {
                    "ok": all(r.get("ok") is True for r in results),
                    "path": str(root),
                    "action": action,
                    "results": results,
                    "scanned_files": scanned_files,
                    "changed_files": changed_files,
                    "written_files": written_files,
                    "match_count": match_count,
                    "replaced_count": replaced_count,
                    "summary": _(
                        "summary.files_changed", default="{count} file(s) changed"
                    ).format(count=changed_files),
                },
                ensure_ascii=False,
            )

        return json.dumps(
            _single_file_edit(
                path=path,
                action=action,
                mode=mode,
                pattern=pattern,
                replacement=replacement,
                preview=preview,
                occurrence=occurrence,
                confirm_over=confirm_over,
                encoding=str(args.get("encoding", "utf-8")),
                expand_newline_tokens=bool(args.get("expand_newline_tokens", True)),
                return_hashes=bool(args.get("return_hashes", False)),
                line_no=line_no,
                po_msgid=po_msgid,
                anchor_before=anchor_before,
                anchor_after=anchor_after,
                mode_after=str(args.get("mode_after", "")) or None,
            ),
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
