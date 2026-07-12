"""diff_files_tool

Compare files or text content and return structured diff output.
Uses Python's standard library `difflib` only -- zero external dependencies.
"""

from __future__ import annotations

import difflib
import json
import os
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:diff_files"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_READ_BYTES = 1_000_000
MAX_DIFF_OUTPUT_LINES = 400
MAX_DIFF_OUTPUT_CHARS = 100_000


# ---------------------------------------------------------------------------
# TOOL_SPEC
# ---------------------------------------------------------------------------
TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "x_parallel_safe": True,
    "function": {
        "name": "diff_files",
        "description": _(
            "tool.description",
            default=(
                "Compare files or text content and return structured diff output. "
                "Supports unified, summary, and json_diff modes."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "diff files",
                "file diff",
                "compare files",
                "difference",
                "unified diff",
                "diff",
                "ux30d5u30a1u30a4u30ebu6bd4u8f03",
                "u5deeu5206",
            ],
        ),
        "x_search_terms_en": [
            "diff files",
            "file diff",
            "compare files",
            "difference",
            "unified diff",
            "diff",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path1": {
                    "type": "string",
                    "description": _(
                        "param.path1.description",
                        default="First file path (required unless path2 is specified).",
                    ),
                },
                "path2": {
                    "type": "string",
                    "description": _(
                        "param.path2.description",
                        default="Second file path. Omit to compare path1 against 'text'.",
                    ),
                },
                "text": {
                    "type": "string",
                    "description": _(
                        "param.text.description",
                        default="Text content to compare against path1 (used when path2 is omitted).",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["unified", "summary", "json_diff"],
                    "description": _(
                        "param.mode.description",
                        default="Output format: unified (default), summary (stats only), json_diff (structured hunk data).",
                    ),
                    "default": "unified",
                },
                "context_lines": {
                    "type": "integer",
                    "description": _(
                        "param.context_lines.description",
                        default="Number of context lines (default: 3).",
                    ),
                    "default": 3,
                },
                "ignore_whitespace": {
                    "type": "boolean",
                    "description": _(
                        "param.ignore_whitespace.description",
                        default="Ignore whitespace-only differences.",
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
                "max_diff_lines": {
                    "type": "integer",
                    "description": _(
                        "param.max_diff_lines.description",
                        default="Max diff output lines for unified/json_diff mode (default: 400, 0=unlimited).",
                    ),
                    "default": 400,
                },
                "path1_label": {
                    "type": "string",
                    "description": _(
                        "param.path1_label.description",
                        default="Custom label for path1 in unified diff header.",
                    ),
                },
                "path2_label": {
                    "type": "string",
                    "description": _(
                        "param.path2_label.description",
                        default="Custom label for path2 in unified diff header.",
                    ),
                },
                "preserve_line_endings": {
                    "type": "boolean",
                    "description": _(
                        "param.preserve_line_endings.description",
                        default="Preserve original line endings (CRLF/CR) in diff output instead of normalizing to LF. Required for patch compatibility with CRLF files.",
                    ),
                    "default": False,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_file_content(path: str, encoding: str, preserve_line_endings: bool = False) -> str:
    """Read a text file safely, respecting workdir boundaries."""
    abspath = ensure_within_workdir(path)
    size = os.path.getsize(abspath)
    if size > MAX_READ_BYTES:
        raise ValueError(
            _(
                "err.file_too_large",
                default="File too large: %(size)s bytes (max %(max_bytes)s)",
            )
            % {"size": size, "max_bytes": MAX_READ_BYTES}
        )
    nl = None if not preserve_line_endings else ""
    with open(abspath, "r", encoding=encoding, errors="replace", newline=nl) as f:
        content = f.read()
    # Normalise line endings to LF unless preserving originals
    if not preserve_line_endings and "\r" in content:
        content = content.replace("\r\n", "\n").replace("\r", "\n")
    return content


def _normalise_text(text: str, ignore_whitespace: bool, preserve_line_endings: bool = False) -> str:
    """Normalise line endings and optionally strip whitespace."""
    if not preserve_line_endings and "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if ignore_whitespace:
        lines = text.splitlines(keepends=True)
        cleaned = []
        for line in lines:
            if line.endswith("\n"):
                cleaned.append(line.rstrip() + "\n")
            elif line.endswith("\r\n"):
                cleaned.append(line.rstrip() + "\r\n")
            elif line.endswith("\r"):
                cleaned.append(line.rstrip() + "\r")
            else:
                cleaned.append(line.rstrip())
        return "".join(cleaned)
    return text


def _compute_unified_diff(
    text1: str,
    text2: str,
    label1: str,
    label2: str,
    ctx_lines: int,
    max_lines: int,
) -> str:
    """Generate unified diff string with size limits."""
    if text1 == text2:
        return ""

    a = text1.splitlines(keepends=True)
    b = text2.splitlines(keepends=True)

    effective_max = max_lines if max_lines > 0 else MAX_DIFF_OUTPUT_LINES

    out: list[str] = []
    out_chars = 0
    out_lines = 0
    truncated = False

    for line in difflib.unified_diff(
        a, b, fromfile=label1, tofile=label2, n=ctx_lines
    ):
        line_len = len(line)
        if (
            out_lines >= effective_max
            or out_chars + line_len > MAX_DIFF_OUTPUT_CHARS
        ):
            truncated = True
            break
        out.append(line)
        out_chars += line_len
        out_lines += 1

    if truncated:
        out.append(
            _(
                "msg.diff_truncated",
                default="\n[diff truncated: max %(max)s lines or %(max_chars)s chars reached]",
            )
            % {"max": effective_max, "max_chars": MAX_DIFF_OUTPUT_CHARS}
        )

    return "".join(out)


def _compute_json_diff(
    text1: str,
    text2: str,
    ctx_lines: int,
    max_lines: int,
) -> list[dict[str, Any]]:
    """Generate structured hunk data for json_diff mode."""
    if text1 == text2:
        return []

    a_lines = text1.splitlines(keepends=True)
    b_lines = text2.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    opcodes = matcher.get_opcodes()

    total_lines_out = 0
    effective_max = max_lines if max_lines > 0 else MAX_DIFF_OUTPUT_LINES

    hunks: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue

        # Build hunk lines
        hunk_lines: list[dict[str, Any]] = []

        # Determine context window
        ctx_start_a = max(0, i1 - ctx_lines)
        ctx_end_a = min(len(a_lines), i2 + ctx_lines)

        # Leading context (from equal block before this change)
        if ctx_start_a < i1:
            for k in range(ctx_start_a, i1):
                hunk_lines.append({"type": "equal", "content": a_lines[k].rstrip("\n").rstrip("\r")})

        # Removed lines
        for k in range(i1, i2):
            hunk_lines.append({"type": "removed", "content": a_lines[k].rstrip("\n").rstrip("\r"), "line_a": k + 1})

        # Added lines
        for k in range(j1, j2):
            hunk_lines.append({"type": "added", "content": b_lines[k].rstrip("\n").rstrip("\r"), "line_b": k + 1})

        # Trailing context (from equal block after this change)
        end_equal_start = i2
        end_equal_end = min(ctx_end_a, len(a_lines))
        if end_equal_start < end_equal_end:
            for k in range(end_equal_start, end_equal_end):
                hunk_lines.append({"type": "equal", "content": a_lines[k].rstrip("\n").rstrip("\r")})

        hunks.append({
            "start_a": i1 + 1,
            "count_a": i2 - i1,
            "start_b": j1 + 1,
            "count_b": j2 - j1,
            "lines": hunk_lines,
        })

        total_lines_out += len(hunk_lines)
        if total_lines_out > effective_max * 3:
            hunks.append({"truncated": True, "reason": "output too large"})
            break

    return hunks


def _compute_stats(text1: str, text2: str) -> dict[str, Any]:
    """Compute statistics about the difference."""
    if text1 == text2:
        return {
            "changed": False,
            "identical": True,
            "added_lines": 0,
            "removed_lines": 0,
            "hunks": 0,
            "similarity_ratio": 1.0,
        }

    a = text1.splitlines(keepends=True)
    b = text2.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, a, b)
    ratio = round(matcher.ratio(), 4)

    added = 0
    removed = 0
    hunks = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks += 1
        removed += i2 - i1
        added += j2 - j1

    return {
        "changed": True,
        "identical": False,
        "added_lines": added,
        "removed_lines": removed,
        "hunks": hunks,
        "similarity_ratio": ratio,
    }


def _make_label(base: str, fallback: str) -> str:
    return base if base else fallback


# ---------------------------------------------------------------------------
# run_tool
# ---------------------------------------------------------------------------
def run_tool(args: dict[str, Any]) -> str:
    try:
        path1 = str(args.get("path1", "") or "").strip()
        path2 = str(args.get("path2", "") or "").strip()
        text = str(args.get("text", "") or "")
        mode = str(args.get("mode", "unified")).strip().lower()
        context_lines = int(args.get("context_lines", 3))
        ignore_whitespace = bool(args.get("ignore_whitespace", False))
        encoding = str(args.get("encoding", "utf-8")).strip()
        max_diff_lines = int(args.get("max_diff_lines", 400))
        label1 = str(args.get("path1_label", "") or "").strip()
        label2 = str(args.get("path2_label", "") or "").strip()
        preserve_line_endings = bool(args.get("preserve_line_endings", False))

        # --- Validation ----------------------------------------------------
        valid_modes = {"unified", "summary", "json_diff"}
        if mode not in valid_modes:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_mode",
                        default="Invalid mode: %(mode)s. Must be one of: %(valid)s",
                    )
                    % {"mode": mode, "valid": ", ".join(sorted(valid_modes))},
                },
                ensure_ascii=False,
            )

        if context_lines < 0:
            context_lines = 0

        if max_diff_lines < 0:
            max_diff_lines = 400

        if not path1 and not path2:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.path_required",
                        default="At least one of path1 or path2 must be specified.",
                    ),
                },
                ensure_ascii=False,
            )

        if path2 and text:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.path2_and_text",
                        default="path2 and text cannot be specified together. Use path1+path2 for file comparison, or path1+text to compare file against string.",
                    ),
                },
                ensure_ascii=False,
            )

        # --- Load content --------------------------------------------------
        content1: str = ""
        content2: str = ""
        resolved_path1: str = ""
        resolved_path2: str = ""

        if path1:
            resolved_path1 = path1
            content1 = _read_file_content(path1, encoding, preserve_line_endings)

        if path2:
            resolved_path2 = path2
            content2 = _read_file_content(path2, encoding, preserve_line_endings)
        elif text:
            resolved_path2 = _("label.text_input", default="<text>")
            content2 = text
        else:
            # path1 only: compare file content against empty string
            resolved_path2 = _("label.empty", default="<empty>")
            content2 = ""

        # --- Normalise -----------------------------------------------------
        norm1 = _normalise_text(content1, ignore_whitespace, preserve_line_endings)
        norm2 = _normalise_text(content2, ignore_whitespace, preserve_line_endings)

        # --- Labels --------------------------------------------------------
        l1 = _make_label(label1, resolved_path1)
        l2 = _make_label(label2, resolved_path2)

        # --- Stats (always computed) ---------------------------------------
        stats = _compute_stats(norm1, norm2)

        # --- Build result --------------------------------------------------
        result: dict[str, Any] = {
            "ok": True,
            "path1": resolved_path1,
            "path2": resolved_path2,
        }
        result.update(stats)

        if mode == "summary":
            return json.dumps(result, ensure_ascii=False)

        if mode == "json_diff":
            hunks = _compute_json_diff(norm1, norm2, context_lines, max_diff_lines)
            result["hunks"] = hunks
            # Source-level summary string for quick reading
            if stats["changed"]:
                result["summary"] = _(
                    "summary.changed",
                    default="%(added)s line(s) added, %(removed)s line(s) removed in %(hunks)s hunk(s)",
                ) % {
                    "added": stats["added_lines"],
                    "removed": stats["removed_lines"],
                    "hunks": stats["hunks"],
                }
            else:
                result["summary"] = _("summary.identical", default="Files are identical.")
            return json.dumps(result, ensure_ascii=False)

        # mode == "unified"
        diff_text = _compute_unified_diff(
            norm1, norm2, l1, l2, context_lines, max_diff_lines
        )
        result["diff"] = diff_text
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        return json.dumps(
            {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            },
            ensure_ascii=False,
        )
