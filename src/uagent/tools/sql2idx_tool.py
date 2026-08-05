from __future__ import annotations

import os
import re
from typing import Any, List, Dict

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "sql2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a SQL script file (.sql) into CREATE TABLE, VIEW, PROCEDURE, and statement blocks, "
                "returning a numbered index or a specific section. Use this when reading large SQL scripts: "
                "call with mode='index' to get statement summaries and line numbers, then call with "
                "mode='section' and section=N to retrieve the SQL definition."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read sql file",
                "sql index",
                "ddl parser",
                "sql section",
                "Read SQL files",
                "SQL index",
                "Table definition",
                "Split into sections",
            ],
        ),
        "x_search_terms_en": [
            "read sql file",
            "sql index",
            "ddl parser",
            "sql section",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the SQL (.sql) file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents of SQL DDL/DML statements. '
                            '"section" returns the SQL definition code of a specific statement.'
                        ),
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default=(
                            "Section number to retrieve (1-indexed, used only when mode='section'). "
                            "Get the number from the index output."
                        ),
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}


class _SqlIndexBuilder:
    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines()
        self.statements: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        pattern = re.compile(
            r"\b(CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW|PROCEDURE|FUNCTION|INDEX|TRIGGER)|ALTER\s+TABLE|INSERT\s+INTO)\s+([`\w\.]+)",
            re.IGNORECASE,
        )

        curr_start = 1
        curr_label = "Initial Script Block"

        for idx, line in enumerate(self.lines, 1):
            match = pattern.search(line)
            if match:
                if idx > curr_start:
                    self.statements.append(
                        {
                            "label": curr_label,
                            "start_line": curr_start,
                            "end_line": idx - 1,
                        }
                    )
                stmt_type = match.group(1).upper()
                obj_name = match.group(2)
                curr_label = f"{stmt_type} {obj_name}"
                curr_start = idx

        if curr_start <= len(self.lines):
            self.statements.append(
                {
                    "label": curr_label,
                    "start_line": curr_start,
                    "end_line": len(self.lines),
                }
            )


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    mode = args.get("mode", "index")
    section = args.get("section")

    try:
        resolved = resolve_index_path(path)
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}").format(e=e)

    if not os.path.isfile(resolved):
        return _("err.file_not_found", default="Error: File not found: {path}").format(
            path=path
        )

    try:
        source = read_index_source(resolved)
        builder = _SqlIndexBuilder(source)
    except Exception as e:
        return _("err.parse_error", default="Error parsing SQL file: {e}").format(e=e)

    if not builder.statements:
        return _("msg.no_statements", default="(no SQL statements found)")

    if mode == "index":
        toc_lines = []
        for idx, stmt in enumerate(builder.statements, 1):
            lbl = stmt["label"]
            s_l = stmt["start_line"]
            e_l = stmt["end_line"]
            toc_lines.append(f"Section {idx:2d}: {lbl} (lines {s_l}-{e_l})")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total sections: {total}\n"
                "To retrieve a statement, call sql2idx with mode='section' and section=N."
            ),
        ).format(path=path, toc=toc, total=len(builder.statements))

    elif mode == "section":
        if section is None:
            return _(
                "err.section_required",
                default="Error: 'section' (integer) is required when mode='section'.",
            )
        try:
            section_num = int(section)
        except (ValueError, TypeError):
            return _(
                "err.section_invalid", default="Error: 'section' must be an integer."
            )

        if section_num < 1 or section_num > len(builder.statements):
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
            ).format(section_num=section_num, last=len(builder.statements))

        target = builder.statements[section_num - 1]
        snippet_lines = []
        for l_num in range(target["start_line"] - 1, target["end_line"]):
            snippet_lines.append(f"{l_num + 1:4d} | {builder.lines[l_num]}")

        return f"=== Section {section_num}: {target['label']} ===\n" + "\n".join(
            snippet_lines
        )

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
