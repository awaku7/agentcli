from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_DEF_RE = re.compile(
    r"^\s*(?:(Public|Private|Protected|Friend|Static)\s+)?"
    r"(Sub|Function|Property\s+(?:Get|Set|Let)|Class|Type|Enum)\b\s*(.*)$",
    re.IGNORECASE,
)
_END_RE = re.compile(
    r"^\s*End\s+(Sub|Function|Property|Class|Type|Enum)\b", re.IGNORECASE
)


def _parse(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    entries: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for number, line in enumerate(lines, 1):
        if active and _END_RE.match(line):
            active["end_line"] = number
            active["text"] = "\n".join(lines[active["line"] - 1 : number])
            entries.append(active)
            active = None
            continue
        if active:
            continue
        match = _DEF_RE.match(line)
        if not match or line.lstrip().startswith("'"):
            continue
        visibility, kind, signature = match.groups()
        kind = re.sub(r"\s+", " ", kind).strip()
        name = signature.split("(", 1)[0].split(" As ", 1)[0].strip()
        active = {
            "line": number,
            "end_line": number,
            "kind": kind,
            "name": name,
            "signature": line.strip(),
            "visibility": visibility or "",
        }
    if active:
        active["text"] = "\n".join(lines[active["line"] - 1 :])
        entries.append(active)
    return entries


def run_tool(args: dict[str, Any]) -> str:
    path = str(args.get("path", "")).strip()
    mode = str(args.get("mode", "index")).strip().lower()
    try:
        if not path:
            raise ValueError("path is required")
        text = Path(path).read_text(encoding="utf-8-sig")
        entries = _parse(text)
        if mode == "index":
            rows = [
                f"[{i}] {e['kind']} {e['name']} (lines {e['line']}-{e['end_line']})"
                for i, e in enumerate(entries, 1)
            ]
            return "\n".join(rows) if rows else "No LotusScript definitions found."
        if mode == "section":
            try:
                section = int(args.get("section", 0))
            except (TypeError, ValueError):
                section = 0
            if section < 1 or section > len(entries):
                raise ValueError(f"section must be between 1 and {len(entries)}")
            return str(entries[section - 1]["text"])
        raise ValueError("mode must be index or section")
    except Exception as exc:
        return f"Error: {exc}"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "index",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "ls2idx",
        "description": _(
            "tool.description",
            default="Parse LotusScript definitions into an index or return one selected section.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "ls2idx",
                "LotusScript",
                "Domino",
                "Notes",
                "Sub",
                "Function",
                "Class",
            ],
        ),
        "x_search_terms_en": [
            "ls2idx",
            "LotusScript",
            "Domino",
            "Notes",
            "Sub",
            "Function",
            "Class",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path", default="Path to a LotusScript source file."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "default": "index",
                    "description": _(
                        "param.mode",
                        default="index for a numbered index, section for one definition.",
                    ),
                },
                "section": {
                    "type": "integer",
                    "minimum": 1,
                    "description": _(
                        "param.section",
                        default="1-based section number when mode is section.",
                    ),
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}
