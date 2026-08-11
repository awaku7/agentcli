from __future__ import annotations

import os
import re
from typing import Any

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "mk2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a Makefile into a numbered index of targets, variables, includes, conditionals, "
                "and define blocks, or return one selected section. Use mode='index' first for a table "
                "of contents, then mode='section' with the section number to read only the required block."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read Makefile",
                "Makefile index",
                "make target list",
                "makefile parser",
                "GNU Make targets",
                "Makefile sections",
                "mk2idx",
            ],
        ),
        "x_search_terms_en": [
            "read Makefile",
            "Makefile index",
            "make target list",
            "makefile parser",
            "GNU Make targets",
            "Makefile sections",
            "mk2idx",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description", default="Path to the Makefile."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default='"index" returns a numbered table of contents; "section" returns one selected block.',
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default="1-based section number, used only when mode='section'.",
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}

_TARGET_RE = re.compile(r"^(?P<indent>\s*)(?P<targets>[^:#=\s][^:]*?):(?:\s|$)")
_VAR_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:?+]?=")
_INCLUDE_RE = re.compile(r"^\s*-?include\s+(.+?)\s*$")
_DEFINE_RE = re.compile(r"^\s*define\s+(.+?)\s*$", re.IGNORECASE)
_END_DEFINE_RE = re.compile(r"^\s*endef\s*$", re.IGNORECASE)
_CONDITIONAL_RE = re.compile(
    r"^\s*(ifn?def|ifn?eq|else|endif|override|private)\b(.*)$", re.IGNORECASE
)


def _logical_lines(source: str) -> list[tuple[int, int, str]]:
    lines = source.splitlines()
    result: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        start = i + 1
        text = lines[i]
        while text.rstrip().endswith("\\") and i + 1 < len(lines):
            i += 1
            text = text.rstrip()[:-1] + " " + lines[i].lstrip()
        result.append((start, i + 1, text))
        i += 1
    return result


def _parse(source: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    lines = source.splitlines()
    logical = _logical_lines(source)
    define_start: tuple[int, str] | None = None
    for start, end, text in logical:
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Recipe lines belong to the preceding target and must not be parsed
        # as variables, directives, or additional targets.
        if text[:1].isspace():
            continue
        if define_start:
            if _END_DEFINE_RE.match(text):
                entries.append(
                    {
                        "type": "define",
                        "name": define_start[1],
                        "start_line": define_start[0],
                        "end_line": end,
                        "label": f"define {define_start[1]}",
                    }
                )
                define_start = None
            continue
        m = _DEFINE_RE.match(text)
        if m:
            define_start = (start, m.group(1).strip())
            continue
        m = _TARGET_RE.match(text)
        if m and not text.lstrip().startswith(("::", "http:")):
            targets = [t.strip() for t in m.group("targets").split() if t.strip()]
            if targets and not all(t.startswith(".") for t in targets):
                entries.append(
                    {
                        "type": "target",
                        "name": " ".join(targets),
                        "start_line": start,
                        "end_line": end,
                        "label": f"target {' '.join(targets)}",
                    }
                )
            continue
        m = _VAR_RE.match(text)
        if m:
            entries.append(
                {
                    "type": "variable",
                    "name": m.group(1),
                    "start_line": start,
                    "end_line": end,
                    "label": f"variable {m.group(1)}",
                }
            )
            continue
        m = _INCLUDE_RE.match(text)
        if m:
            entries.append(
                {
                    "type": "include",
                    "name": m.group(1).strip(),
                    "start_line": start,
                    "end_line": end,
                    "label": f"include {m.group(1).strip()}",
                }
            )
            continue
        m = _CONDITIONAL_RE.match(text)
        if m:
            entries.append(
                {
                    "type": "directive",
                    "name": (m.group(1) + " " + m.group(2)).strip(),
                    "start_line": start,
                    "end_line": end,
                    "label": f"directive {(m.group(1) + ' ' + m.group(2)).strip()}",
                }
            )
    # Extend target sections through their recipe body, stopping at the next
    # top-level Makefile definition. Trim trailing blank lines.
    for index, entry in enumerate(entries):
        if entry["type"] != "target":
            continue
        next_start = (
            entries[index + 1]["start_line"]
            if index + 1 < len(entries)
            else len(lines) + 1
        )
        end_line = next_start - 1
        while end_line >= entry["start_line"] and not lines[end_line - 1].strip():
            end_line -= 1
        entry["end_line"] = max(entry["start_line"], end_line)
    return entries


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")
    try:
        resolved = resolve_index_path(path)
    except Exception as exc:
        return _("err.read_error", default="Error reading file: {e}").format(e=exc)
    if not os.path.isfile(resolved):
        return _("err.file_not_found", default="Error: File not found: {path}").format(
            path=path
        )
    try:
        entries = _parse(read_index_source(resolved))
        mode = str(args.get("mode", "index")).lower()
        if mode == "index":
            if not entries:
                return _("msg.no_entries", default="No Makefile definitions found.")
            return "\n".join(
                f"[{i}] {e['label']} (lines {e['start_line']}-{e['end_line']})"
                for i, e in enumerate(entries, 1)
            )
        if mode != "section":
            return _(
                "err.invalid_mode", default="Error: mode must be 'index' or 'section'."
            )
        try:
            section = int(args.get("section", 0))
        except (TypeError, ValueError):
            section = 0
        if section < 1 or section > len(entries):
            return _(
                "err.invalid_section",
                default="Error: section must be between 1 and {count}.",
            ).format(count=len(entries))
        item = entries[section - 1]
        lines = read_index_source(resolved).splitlines()
        return "\n".join(lines[item["start_line"] - 1 : item["end_line"]])
    except Exception as exc:
        return _("err.parse_error", default="Error parsing Makefile: {e}").format(e=exc)
