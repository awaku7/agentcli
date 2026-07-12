"""apply_patch_tool

Apply unified diff (patch) to files using pure Python (difflib).
No git or external patch command required.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir, make_backup_before_overwrite

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:apply_patch"

MAX_READ_BYTES = 1_000_000
MAX_DIFF_OUTPUT_CHARS = 100_000
MAX_DIFF_OUTPUT_LINES = 400

# ---------------------------------------------------------------------------
# TOOL_SPEC
# ---------------------------------------------------------------------------
TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "function": {
        "name": "apply_patch",
        "description": _(
            "tool.description",
            default=(
                "Apply a unified diff (patch) to files using pure Python. "
                "Supports dry-run preview, whitespace tolerance, and CRLF preservation."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "apply patch",
                "patch file",
                "apply diff",
                "unified diff apply",
                "ux30d1ux30c3ux30c1ux9069ux7528",
            ],
        ),
        "x_search_terms_en": [
            "apply patch",
            "patch file",
            "apply diff",
            "unified diff apply",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "patch_text": {
                    "type": "string",
                    "description": _(
                        "param.patch_text.description",
                        default="Unified diff text to apply (git-format compatible, e.g. ---/+++ headers).",
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": _(
                        "param.dry_run.description",
                        default="If true, only preview what would be changed without applying.",
                    ),
                    "default": True,
                },
                "ignore_whitespace": {
                    "type": "boolean",
                    "description": _(
                        "param.ignore_whitespace.description",
                        default="Ignore whitespace differences when matching context lines.",
                    ),
                    "default": False,
                },
                "encoding": {
                    "type": "string",
                    "description": _(
                        "param.encoding.description",
                        default="File encoding (default: utf-8).",
                    ),
                    "default": "utf-8",
                },
                "preserve_line_endings": {
                    "type": "boolean",
                    "description": _(
                        "param.preserve_line_endings.description",
                        default="Preserve original line endings (CRLF/CR) in output.",
                    ),
                    "default": False,
                },
                "revert": {
                    "type": "boolean",
                    "description": _(
                        "param.revert.description",
                        default="Apply the patch in reverse (swap added/removed lines).",
                    ),
                    "default": False,
                },
                "strip": {
                    "type": "integer",
                    "description": _(
                        "param.strip.description",
                        default="Strip N leading path components from file paths in patch headers (like git apply -pN).",
                    ),
                    "default": 0,
                },
            },
            "required": ["patch_text"],
        },
    },
}


# ---------------------------------------------------------------------------
# Patch parsing
# ---------------------------------------------------------------------------
_HUNK_HEADER_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@"
)
_PATH_HEADER_RE = re.compile(r"^(?:---|\+\+\+)\s+(?:\S/)?(?P<path>.+)$")


@dataclass
class _Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


@dataclass
class _PatchFile:
    target_path: str
    hunks: list[_Hunk]


def _flush_patch(patches: list[_PatchFile], path: str, hunks: list[_Hunk]) -> None:
    if path and hunks:
        patches.append(_PatchFile(target_path=path, hunks=list(hunks)))
        hunks.clear()


def _parse_patch(patch_text: str) -> list[_PatchFile]:
    """Parse unified diff text into structured patch entries."""
    if "\r" in patch_text:
        patch_text = patch_text.replace("\r\n", "\n").replace("\r", "\n")

    lines = patch_text.splitlines(keepends=True)
    patches: list[_PatchFile] = []
    current_path = ""
    current_hunks: list[_Hunk] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        m = _PATH_HEADER_RE.match(line.strip())
        if m and line.startswith("+++"):
            _flush_patch(patches, current_path, current_hunks)
            current_path = ""
            path = m.group("path").strip()
            if path.startswith("a/") or path.startswith("b/"):
                path = path[2:]
            current_path = path
            i += 1
            continue
        elif m and line.startswith("---"):
            i += 1
            continue

        m = _HUNK_HEADER_RE.match(line.strip())
        if m:
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) else 1
            hunk_lines: list[str] = []
            i += 1
            while i < len(lines):
                nl = lines[i]
                if nl.startswith("@@") and _HUNK_HEADER_RE.match(nl.strip()):
                    break
                if nl.startswith("---") or nl.startswith("+++"):
                    break
                hunk_lines.append(nl)
                i += 1
            current_hunks.append(_Hunk(
                old_start=old_start, old_count=old_count,
                new_start=new_start, new_count=new_count,
                lines=hunk_lines,
            ))
            continue
        i += 1

    _flush_patch(patches, current_path, current_hunks)
    return patches


# ---------------------------------------------------------------------------
# Hunk application
# ---------------------------------------------------------------------------
def _detect_newline(text: str) -> str:
    crlf = text.count("\r\n")
    lf_only = text.count("\n") - crlf
    cr_only = text.count("\r") - crlf
    if crlf > lf_only and crlf > cr_only:
        return "\r\n"
    return "\n"


def _convert_newlines(lines: list[str], target_nl: str) -> list[str]:
    if target_nl == "\n":
        return [l.replace("\r\n", "\n").replace("\r", "\n") for l in lines]
    result: list[str] = []
    for l in lines:
        s = l.replace("\r\n", "\n").replace("\r", "\n")
        if s.endswith("\n"):
            s = s[:-1] + "\r\n"
        result.append(s)
    return result


def _strip_line_ending(s: str) -> str:
    if s.endswith("\r\n"):
        return s[:-2]
    if s.endswith("\n") or s.endswith("\r"):
        return s[:-1]
    return s


def _build_before_lines(hunk: _Hunk) -> list[str]:
    result: list[str] = []
    for line in hunk.lines:
        if not line:
            continue
        pr = line[0]
        if pr in (" ", "-"):
            result.append(line[1:])
    return result


def _build_after_lines(hunk: _Hunk) -> list[str]:
    result: list[str] = []
    for line in hunk.lines:
        if not line:
            continue
        pr = line[0]
        if pr in (" ", "+"):
            result.append(line[1:])
    return result


def _normalize_compare(s: str, ignore_whitespace: bool) -> str:
    s = _strip_line_ending(s)
    if ignore_whitespace:
        s = s.rstrip()
    return s


def _compute_fuzzy_threshold(before_lines: list[str]) -> int:
    """Minimum matching character count for fuzzy match (60% or 8 chars min)."""
    total_chars = sum(len(l.rstrip("\n").rstrip("\r")) for l in before_lines)
    return max(8, int(total_chars * 0.6))


def _find_hunk_position(
    text_lines: list[str],
    before_lines: list[str],
    start_line: int,
    ignore_whitespace: bool,
) -> int | None:
    if not before_lines:
        return min(start_line, len(text_lines))

    n_before = len(before_lines)
    n_text = len(text_lines)
    if n_before > n_text:
        return None

    norm_before = [_normalize_compare(l, ignore_whitespace) for l in before_lines]

    # Exact match: search outward from hint
    search_start = min(start_line, n_text - n_before)
    seen: set[int] = set()
    for offset in range(n_text - n_before + 1):
        for pos in (search_start + offset, search_start - offset):
            if 0 <= pos <= n_text - n_before and pos not in seen:
                seen.add(pos)
                ok = True
                for j in range(n_before):
                    if _normalize_compare(text_lines[pos + j], ignore_whitespace) != norm_before[j]:
                        ok = False
                        break
                if ok:
                    return pos

    # Fuzzy match: SequenceMatcher, require 60% chars or 8 chars minimum
    before_text = "\n".join(norm_before)
    text_block = "\n".join(_normalize_compare(l, ignore_whitespace) for l in text_lines)
    if not before_text or not text_block:
        return None

    threshold = _compute_fuzzy_threshold(before_lines)
    matcher = difflib.SequenceMatcher(None, before_text, text_block)
    best_pos = None
    best_size = 0
    for m in matcher.get_matching_blocks():
        if m.size > best_size and m.size >= threshold:
            line_pos = text_block[:m.b].count("\n")
            if 0 <= line_pos <= n_text - n_before:
                best_pos = line_pos
                best_size = m.size
    return best_pos


def _apply_hunk_to_text(
    text: str,
    hunk: _Hunk,
    ignore_whitespace: bool,
    revert: bool,
    preserve: bool,
) -> tuple[str, bool, str]:
    text_lines = text.splitlines(keepends=True)
    before = _build_before_lines(hunk)
    after = _build_after_lines(hunk)

    if revert:
        before, after = after, before

    if preserve:
        target_nl = _detect_newline(text)
        after = _convert_newlines(after, target_nl)

    hint_line = max(0, min(hunk.old_start - 1, len(text_lines) - 1))
    pos = _find_hunk_position(text_lines, before, hint_line, ignore_whitespace)

    if pos is None:
        return text, False, ""

    new_lines = text_lines[:pos] + after + text_lines[pos + len(before):]
    new_text = "".join(new_lines)

    diff_preview = "".join(difflib.unified_diff(
        text_lines[pos:pos + len(before)], after,
        fromfile="a/original", tofile="b/modified", n=2
    ))[:2000]

    return new_text, True, diff_preview


def _strip_path(path: str, strip: int) -> str:
    if strip <= 0:
        return path
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[strip:])


def _read_file(path: str, encoding: str, preserve: bool) -> str:
    abspath = ensure_within_workdir(path)
    size = os.path.getsize(abspath)
    if size > MAX_READ_BYTES:
        raise ValueError(
            _("err.file_too_large", default="File too large: %(size)s bytes (max %(max_bytes)s)")
            % {"size": size, "max_bytes": MAX_READ_BYTES}
        )
    nl = "" if preserve else None
    with open(abspath, "r", encoding=encoding, errors="replace", newline=nl) as f:
        content = f.read()
    if not preserve and "\r" in content:
        content = content.replace("\r\n", "\n").replace("\r", "\n")
    return content


def _write_file(path: str, text: str, encoding: str, preserve: bool) -> None:
    abspath = ensure_within_workdir(path)
    nl = "" if preserve else None
    with open(abspath, "w", encoding=encoding, newline=nl) as f:
        f.write(text)


# ---------------------------------------------------------------------------
# run_tool
# ---------------------------------------------------------------------------
def run_tool(args: dict[str, Any]) -> str:
    try:
        patch_text = str(args.get("patch_text", "") or "")
        dry_run = bool(args.get("dry_run", True))
        ignore_whitespace = bool(args.get("ignore_whitespace", False))
        encoding = str(args.get("encoding", "utf-8")).strip()
        preserve_line_endings = bool(args.get("preserve_line_endings", False))
        revert = bool(args.get("revert", False))
        strip = int(args.get("strip", 0))

        if not patch_text.strip():
            return json.dumps(
                {"ok": False, "error": _("err.patch_empty", default="patch_text is empty.")},
                ensure_ascii=False,
            )

        patch_files = _parse_patch(patch_text)
        if not patch_files:
            return json.dumps(
                {"ok": False, "error": _("err.no_hunks", default="No valid hunks found in patch text.")},
                ensure_ascii=False,
            )

        results: list[dict[str, Any]] = []
        total_added = 0
        total_removed = 0
        total_hunks = 0
        total_applied = 0
        all_ok = True

        for pf in patch_files:
            target = _strip_path(pf.target_path, strip)
            file_result: dict[str, Any] = {
                "target": target,
                "hunks_total": len(pf.hunks),
                "hunks_applied": 0,
                "hunks_failed": 0,
                "changed": False,
            }

            try:
                content = _read_file(target, encoding, preserve_line_endings)
            except Exception as e:
                file_result["error"] = str(e)
                file_result["ok"] = False
                all_ok = False
                results.append(file_result)
                continue

            current = content
            applied_hunks = 0
            failed_hunks = 0
            hunk_details: list[dict[str, Any]] = []

            for hunk in pf.hunks:
                new_text, applied, diff = _apply_hunk_to_text(
                    current, hunk, ignore_whitespace, revert, preserve_line_endings
                )
                if applied:
                    current = new_text
                    applied_hunks += 1
                    total_applied += 1
                    for hl in hunk.lines:
                        p = hl[0] if hl else " "
                        if p == "+":
                            total_added += 1
                        elif p == "-":
                            total_removed += 1
                    hunk_details.append({"applied": True, "old_start": hunk.old_start, "diff_preview": diff[:500]})
                else:
                    failed_hunks += 1
                    hunk_details.append({
                        "applied": False, "old_start": hunk.old_start,
                        "error": _("err.hunk_not_found", default="Context not found in file."),
                    })

            file_result["hunks_applied"] = applied_hunks
            file_result["hunks_failed"] = failed_hunks
            file_result["changed"] = applied_hunks > 0
            file_result["ok"] = failed_hunks == 0
            if failed_hunks > 0:
                all_ok = False

            if dry_run:
                file_result["dry_run"] = True
            else:
                if applied_hunks > 0:
                    try:
                        backup = make_backup_before_overwrite(target)
                        _write_file(target, current, encoding, preserve_line_endings)
                        file_result["backup"] = backup
                    except Exception as e:
                        file_result["error"] = str(e)
                        file_result["ok"] = False
                        all_ok = False

            file_result["hunks"] = hunk_details
            results.append(file_result)
            total_hunks += len(pf.hunks)

        summary = _(
            "summary.applied",
            default="%(applied)s of %(total)s hunk(s) applied to %(files)s file(s). "
                    "%(added)s line(s) added, %(removed)s line(s) removed.",
        ) % {
            "applied": total_applied, "total": total_hunks,
            "files": len(patch_files), "added": total_added, "removed": total_removed,
        }

        return json.dumps({
            "ok": all_ok, "dry_run": dry_run, "summary": summary,
            "files": results, "total_hunks": total_hunks,
            "total_applied": total_applied, "total_added": total_added,
            "total_removed": total_removed,
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
