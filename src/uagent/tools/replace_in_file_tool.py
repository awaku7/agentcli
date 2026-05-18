"""replace_in_file_tool

Safely performs literal or regular-expression replacements on an existing text file.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
            else _("summary.no_change", default="Successfully no change (0 matches)")
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


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "replace_in_file",
        "description": _(
            "tool.description",
            default=(
                "Safely edit text files. Newline handling: by default, the "
                "two-character tokens \\r\\n, \\r, and \\n in pattern/replacement "
                "are converted to real newlines before matching. Set "
                "expand_newline_tokens=false to match those backslash characters "
                "literally. Existing file newline style is preserved when writing."
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
                            "If true (default), convert the literal token strings "
                            "\\r\\n, \\r, and \\n in pattern/replacement/anchors "
                            "to real newlines before matching. If false, keep those "
                            "backslash characters literal. JSON actual newlines are "
                            "accepted either way."
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
                        default=(
                            "Replacement mode: literal (plain substring) or regex (Python re). "
                            "If you use regex, escape backslashes in JSON strings, for example \\d, \\s, and \\."
                        ),
                    ),
                    "default": "literal",
                },
                "pattern": {
                    "type": "string",
                    "description": _(
                        "param.pattern.description",
                        default="Search pattern. Use \\n for newlines. In JSON strings, write backslash sequences as \\\\n.",
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
                        default="Target gettext msgid for replace_po_entry. If omitted, pattern is used as a fallback.",
                    ),
                },
                "anchor_before": {
                    "type": "string",
                    "description": _(
                        "param.anchor_before.description",
                        default="Start anchor for replace_between (literal or regex depending on mode).",
                    ),
                },
                "anchor_after": {
                    "type": "string",
                    "description": _(
                        "param.anchor_after.description",
                        default="End anchor for replace_between (literal or regex depending on mode).",
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
                        "replace_between",
                        "replace_po_entry",
                        "replace_all_in_files",
                    ],
                    "description": _(
                        "param.action.description",
                        default="Operation: replace, append, insert_at_end, insert_before, insert_after, insert_at_line, replace_between, replace_po_entry, or replace_all_in_files.",
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
                        default="Recursively scan under the target directory.",
                    ),
                    "default": True,
                },
            },
            "required": ["path", "replacement", "pattern"],
        },
    },
}


def _read_text_robust(path: str, encoding: str, max_bytes: int) -> Tuple[str, Any, str]:
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
    if original == replaced:
        return ""
    a = original.splitlines(True)
    b = replaced.splitlines(True)
    return "".join(difflib.unified_diff(a, b, fromfile=f"a/{path}", tofile=f"b/{path}"))


def _write_text_robust(path: str, text: str, encoding: str) -> None:
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)


def _expand_newline_tokens_to_lf(s: str) -> str:
    return (
        s.replace("\\r\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\n", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


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
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if target != "\n":
        text = text.replace("\n", target)
    return text


def _normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass
class _Hit:
    start: int
    end: int


def _map_idx_to_line_col(text: str, idx: int) -> Tuple[int, int]:
    line_no = text.count("\n", 0, idx) + 1
    last_nl = text.rfind("\n", 0, idx)
    col = idx if last_nl < 0 else idx - last_nl - 1
    return line_no, col


def _extract_same_line_context(text: str, start: int, end: int) -> Tuple[str, str, str]:
    l_start = text.rfind("\n", 0, start)
    l_start = 0 if l_start < 0 else l_start + 1
    l_end = text.find("\n", end)
    l_end = len(text) if l_end < 0 else l_end
    return text[l_start:start], text[start:end], text[end:l_end]


def _find_hits_literal(haystack: str, needle: str) -> List[_Hit]:
    hits: List[_Hit] = []
    start = 0
    if not needle:
        return hits
    while True:
        pos = haystack.find(needle, start)
        if pos < 0:
            break
        hits.append(_Hit(pos, pos + len(needle)))
        start = pos + len(needle)
    return hits


def _find_hits_regex(haystack: str, pattern: re.Pattern[str]) -> List[_Hit]:
    return [_Hit(m.start(), m.end()) for m in pattern.finditer(haystack)]


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _newline_details(newline: Any, selected_style: str) -> Dict[str, Any]:
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


def _text_newline_flags(text: str) -> Dict[str, Any]:
    return {
        "contains_actual_newline": "\n" in text or "\r" in text,
        "contains_escaped_newline_tokens": "\\n" in text or "\\r" in text,
        "repr": repr(text),
    }


def _diagnostics_hint(diagnostics: Dict[str, Any] | None) -> str | None:
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


def _po_encode_msgstr(text: str) -> List[str]:
    normalized = _normalize_lf(text)
    if normalized == "":
        return ['msgstr ""\n']
    if "\n" not in normalized and "\r" not in normalized:
        return [f'msgstr "{_po_escape_text(normalized)}"\n']

    out = ['msgstr ""\n']
    for part in normalized.splitlines(keepends=True):
        out.append(f'"{_po_escape_text(part)}"\n')
    return out


def _po_parse_entry_block(block_lines: List[str]) -> Dict[str, Any] | None:
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
    newline_info: Dict[str, Any] | None = None,
    anchor_before: str = "",
    anchor_after: str = "",
    po_msgid: str = "",
) -> Dict[str, Any]:
    search_flags = _text_newline_flags(search_text)
    diagnostics: Dict[str, Any] = {
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

    if action == "replace_between":
        diagnostics["anchor_before"] = anchor_before
        diagnostics["anchor_after"] = anchor_after
        diagnostics["anchor_before_flags"] = _text_newline_flags(anchor_before)
        diagnostics["anchor_after_flags"] = _text_newline_flags(anchor_after)
        diagnostics["anchor_before_found"] = bool(
            anchor_before and anchor_before in original
        )
        diagnostics["anchor_after_found"] = bool(
            anchor_after and anchor_after in original
        )
        if anchor_before and not diagnostics["anchor_before_found"]:
            hints.append(
                _(
                    "hint.anchor_before_not_found",
                    default="anchor_before was not found.",
                )
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
    newline_info: Dict[str, Any],
) -> tuple[str, int, int, List[Dict[str, Any]], Dict[str, Any] | None]:
    lines = original.splitlines(keepends=True)
    out: list[str] = []
    match_hits: List[Dict[str, Any]] = []
    match_total = 0
    replaced_total = 0
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
            if len(match_hits) < 20:
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
        diag["msgstr_is_empty"] = any(hit.get("msgstr_is_empty") for hit in match_hits)
        diag["msgstr_kinds"] = sorted(
            {
                str(hit.get("msgstr_kind"))
                for hit in match_hits
                if hit.get("msgstr_kind")
            }
        )
        diag["msgstr_line_counts"] = sorted(
            {
                int(hit.get("msgstr_line_count", 0))
                for hit in match_hits
                if hit.get("msgstr_line_count") is not None
            }
        )
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
        "msgstr_is_empty": any(hit.get("msgstr_is_empty") for hit in match_hits),
        "msgstr_kinds": sorted(
            {
                str(hit.get("msgstr_kind"))
                for hit in match_hits
                if hit.get("msgstr_kind")
            }
        ),
        "msgstr_line_counts": sorted(
            {
                int(hit.get("msgstr_line_count", 0))
                for hit in match_hits
                if hit.get("msgstr_line_count") is not None
            }
        ),
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
    newline_info: Dict[str, Any],
) -> tuple[str, int, int, List[Dict[str, Any]], Dict[str, Any] | None]:
    before_hits = (
        _find_hits_regex(original, re.compile(anchor_before))
        if mode == "regex"
        else _find_hits_literal(original, anchor_before)
    )
    if not before_hits:
        return (
            original,
            0,
            0,
            [],
            _build_no_match_diagnostics(
                original=original,
                search_text=anchor_before,
                mode=mode,
                action="replace_between",
                expand_newline_tokens=expand_newline_tokens,
                newline_info=newline_info,
                anchor_before=anchor_before,
                anchor_after=anchor_after,
            ),
        )

    if occurrence <= 0:
        before_hit = before_hits[0]
    elif occurrence <= len(before_hits):
        before_hit = before_hits[occurrence - 1]
    else:
        diag = _build_no_match_diagnostics(
            original=original,
            search_text=anchor_before,
            mode=mode,
            action="replace_between",
            expand_newline_tokens=expand_newline_tokens,
            newline_info=newline_info,
            anchor_before=anchor_before,
            anchor_after=anchor_after,
        )
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
        return original, len(before_hits), 0, [], diag

    after_hits = (
        _find_hits_regex(original, re.compile(anchor_after))
        if mode == "regex"
        else _find_hits_literal(original, anchor_after)
    )
    after_hits = [hit for hit in after_hits if hit.start >= before_hit.end]
    if not after_hits:
        diag = _build_no_match_diagnostics(
            original=original,
            search_text=anchor_after,
            mode=mode,
            action="replace_between",
            expand_newline_tokens=expand_newline_tokens,
            newline_info=newline_info,
            anchor_before=anchor_before,
            anchor_after=anchor_after,
        )
        diag["hints"] = [
            _(
                "hint.anchor_after_not_found_after_before",
                default="anchor_after was not found after anchor_before.",
            ),
            *diag["hints"],
        ]
        return original, len(before_hits), 0, [], diag

    after_hit = after_hits[0]
    replaced_text = (
        original[: before_hit.end] + replacement + original[after_hit.start :]
    )
    lno, col = _map_idx_to_line_col(original, before_hit.start)
    match_hits = [
        {
            "line_no": lno,
            "col": col,
            "anchor_before": anchor_before,
            "anchor_after": anchor_after,
            "block_before": original[before_hit.start : before_hit.end],
            "block_after": original[after_hit.start : after_hit.end],
        }
    ]
    return replaced_text, len(before_hits), 1, match_hits, None


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
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if newline == "\n":
        return text
    return text.replace("\n", newline)


def run_tool(args: Dict[str, Any]) -> str:
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
    ) -> Dict[str, Any]:
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

        hits: List[_Hit] = []
        if action in {"replace", "insert_before", "insert_after"}:
            if mode == "regex":
                hits = _find_hits_regex(orig_norm, re.compile(p2))
            else:
                hits = _find_hits_literal(orig_norm, p2)

        match_count = len(hits)
        replaced_text = orig_norm
        replaced_count = 0
        match_hits: List[Dict[str, Any]] = []
        backup_path = None
        diagnostics: Dict[str, Any] | None = None

        if action == "replace_po_entry":
            target = po_target or p2
            if not target:
                raise ValueError("po_msgid is required for replace_po_entry")
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
                    "anchor_before and anchor_after are required for replace_between"
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
                )
            )
        elif action == "replace" and match_count > 0:
            if occurrence == 0:
                if mode == "regex":
                    replaced_text, replaced_count = re.compile(p2).subn(r2, orig_norm)
                else:
                    replaced_text = orig_norm.replace(p2, r2)
                    replaced_count = match_count
            elif 0 < occurrence <= match_count:
                h = hits[occurrence - 1]
                if mode == "regex":
                    m = list(re.compile(p2).finditer(orig_norm))[occurrence - 1]
                    replaced_text = (
                        orig_norm[: h.start] + m.expand(r2) + orig_norm[h.end :]
                    )
                else:
                    replaced_text = orig_norm[: h.start] + r2 + orig_norm[h.end :]
                replaced_count = 1
            for h in hits[:50]:
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

        elif action in {"insert_before", "insert_after"} and hits:
            h = hits[occurrence - 1 if 0 < occurrence <= match_count else 0]
            if action == "insert_before":
                idx = orig_norm.rfind("\n", 0, h.start)
                ins_at = 0 if idx < 0 else idx + 1
            else:
                idx = orig_norm.find("\n", h.end)
                ins_at = len(orig_norm) if idx < 0 else idx + 1
            replaced_text = orig_norm[:ins_at] + r2 + orig_norm[ins_at:]
            replaced_count = 1

        elif action == "insert_at_line":
            lines = orig_norm.splitlines(True)
            if 1 <= line_no <= len(lines) + 1:
                off = sum(len(line) for line in lines[: line_no - 1])
                replaced_text = orig_norm[:off] + r2 + orig_norm[off:]
                replaced_count = 1
            match_count = replaced_count

        elif action == "insert_at_end":
            replaced_text = orig_norm + r2
            replaced_count = 1
            match_count = 1

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
                search_text=p2,
                mode=mode,
                action=action,
                expand_newline_tokens=expand_newline_tokens,
                newline_info=newline_info,
            )
            hint = _diagnostics_hint(diagnostics)
        if (
            hint is None
            and match_count == 0
            and action in {"replace", "insert_before", "insert_after"}
        ):
            hint = _get_failure_hint(orig_norm, p2, mode)

        changed = replaced_text != orig_norm
        if (
            not preview
            and action in {"replace", "replace_po_entry", "replace_between"}
            and occurrence == 0
            and match_count > confirm_over
        ):
            return {
                "ok": True,
                "path": path,
                "match_count": match_count,
                "changed": False,
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
        if action == "append":
            action = "insert_at_end"
        pattern = str(args.get("pattern", ""))
        replacement = str(args.get("replacement", ""))
        preview = bool(args.get("preview", True))
        occurrence = int(args.get("occurrence", 0))
        confirm_over = int(args.get("confirm_over", 10))
        line_no = int(args.get("line_no", 0))
        po_msgid = str(args.get("po_msgid", args.get("msgid", "")))
        anchor_before = str(args.get("anchor_before", ""))
        anchor_after = str(args.get("anchor_after", ""))

        if not path:
            return json.dumps(
                {
                    "ok": False,
                    "error": _("err.path_missing", default="path is not specified"),
                },
                ensure_ascii=False,
            )

        if action == "replace_all_in_files":
            root = Path(ensure_within_workdir(path))
            if root.is_file():
                targets = [root]
            else:
                globber = root.rglob if bool(args.get("recursive", True)) else root.glob
                targets = [
                    p for p in globber(args.get("name_pattern", "*")) if p.is_file()
                ]
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
                    "ok": True,
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
            ),
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
