from __future__ import annotations

import os
import csv
from typing import Any, List, Dict

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "csv2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a CSV or TSV file (.csv/.tsv) into header previews and row block summaries, "
                "returning a numbered index or a specific section. Use this when reading large CSV files: "
                "call with mode='index' to get headers and row block ranges, then call with "
                "mode='section' and section=N to retrieve the rows of that block."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read csv file",
                "csv index",
                "csv parser",
                "tsv reader",
                "CSVファイルを読む",
                "CSVインデックス",
                "行ブロック分割",
                "セクション分割",
            ],
        ),
        "x_search_terms_en": [
            "read csv file",
            "csv index",
            "csv parser",
            "tsv reader",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the CSV/TSV file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents listing row blocks. '
                            '"section" returns the table content of a specific row block.'
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
                "block_size": {
                    "type": "integer",
                    "description": _(
                        "param.block_size.description",
                        default="Number of rows per block (default 100).",
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}


class _CsvIndexBuilder:
    def __init__(self, source: str, filepath: str, block_size: int = 100):
        self.source = source
        self.filepath = filepath
        self.block_size = block_size
        self.headers: List[str] = []
        self.blocks: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        lines = self.source.splitlines()
        if not lines:
            return

        delimiter = "\t" if self.filepath.lower().endswith(".tsv") else ","
        reader = csv.reader(lines, delimiter=delimiter)

        all_rows = list(reader)
        if not all_rows:
            return

        self.headers = all_rows[0]
        data_rows = all_rows[1:]

        if not data_rows:
            self.blocks.append(
                {"block_num": 1, "start_row": 1, "end_row": 1, "rows": []}
            )
            return

        total_data = len(data_rows)
        for i in range(0, total_data, self.block_size):
            chunk = data_rows[i : i + self.block_size]
            start_r = i + 2
            end_r = i + 1 + len(chunk)
            self.blocks.append(
                {
                    "block_num": len(self.blocks) + 1,
                    "start_row": start_r,
                    "end_row": end_r,
                    "rows": chunk,
                }
            )


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    mode = args.get("mode", "index")
    section = args.get("section")
    block_size = args.get("block_size", 100)

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
        builder = _CsvIndexBuilder(source, resolved, block_size=block_size)
    except Exception as e:
        return _("err.parse_error", default="Error parsing CSV file: {e}").format(e=e)

    if not builder.blocks:
        return _("msg.no_entries", default="(no data rows found in CSV)")

    if mode == "index":
        header_str = (
            ", ".join(builder.headers[:6]) if builder.headers else "(no headers)"
        )
        if len(builder.headers) > 6:
            header_str += ", ..."

        toc_lines = [f"Headers: {header_str}\n---"]
        for b in builder.blocks:
            b_num = b["block_num"]
            s_r = b["start_row"]
            e_r = b["end_row"]
            toc_lines.append(
                f"Block {b_num:3d}: Rows {s_r}-{e_r} ({len(b['rows'])} rows)"
            )

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total blocks: {total}\n"
                "To retrieve rows, call csv2idx with mode='section' and section=N."
            ),
        ).format(path=path, toc=toc, total=len(builder.blocks))

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

        if section_num < 1 or section_num > len(builder.blocks):
            return _(
                "err.section_not_found",
                default="Error: Block {section_num} not found. Valid range: 1..{last}.",
            ).format(section_num=section_num, last=len(builder.blocks))

        target = builder.blocks[section_num - 1]
        out_lines = [
            f"=== Block {target['block_num']} (Rows {target['start_row']}-{target['end_row']}) ==="
        ]
        if builder.headers:
            out_lines.append("Header | " + " | ".join(builder.headers))

        for idx, r in enumerate(target["rows"], target["start_row"]):
            out_lines.append(f"{idx:6d} | " + " | ".join(r))

        return "\n".join(out_lines)

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
