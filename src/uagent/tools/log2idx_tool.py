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
        "name": "log2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a log file (.log/.txt) into timestamp blocks, error/warning events, and line ranges, "
                "returning a numbered index or a specific section. Use this when reading large log files: "
                "call with mode='index' to get log block summaries and error event locations, then call with "
                "mode='section' and section=N to retrieve that log block."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read log file",
                "log index",
                "log parser",
                "log section",
                "ログファイルを読む",
                "ログインデックス",
                "エラー抽出",
                "セクション分割",
            ],
        ),
        "x_search_terms_en": [
            "read log file",
            "log index",
            "log parser",
            "log section",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the log (.log/.txt) file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents of log blocks and error events. '
                            '"section" returns lines of a specific log block.'
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
                "block_lines": {
                    "type": "integer",
                    "description": _(
                        "param.block_lines.description",
                        default="Number of lines per log block (default 200).",
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}


class _LogIndexBuilder:
    def __init__(self, source: str, block_lines: int = 200):
        self.source = source
        self.lines = source.splitlines()
        self.block_lines = block_lines
        self.blocks: List[Dict[str, Any]] = []
        self._parse()

    def _parse(self) -> None:
        if not self.lines:
            return

        level_pattern = re.compile(
            r"\b(ERROR|WARN|WARNING|CRITICAL|FATAL)\b", re.IGNORECASE
        )

        total_lines = len(self.lines)
        for i in range(0, total_lines, self.block_lines):
            chunk = self.lines[i : i + self.block_lines]
            start_l = i + 1
            end_l = i + len(chunk)

            # Detect errors in chunk
            errors = []
            for l_idx, line in enumerate(chunk, start_l):
                m = level_pattern.search(line)
                if m:
                    errors.append(f"L{l_idx}: {m.group(1).upper()}")

            err_summary = f" [Events: {', '.join(errors[:3])}]" if errors else ""
            if len(errors) > 3:
                err_summary += f" (+{len(errors) - 3} more)"

            self.blocks.append(
                {
                    "block_num": len(self.blocks) + 1,
                    "start_line": start_l,
                    "end_line": end_l,
                    "summary": f"Lines {start_l}-{end_l}{err_summary}",
                }
            )


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    mode = args.get("mode", "index")
    section = args.get("section")
    block_lines = args.get("block_lines", 200)

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
        builder = _LogIndexBuilder(source, block_lines=block_lines)
    except Exception as e:
        return _("err.parse_error", default="Error parsing log file: {e}").format(e=e)

    if not builder.blocks:
        return _("msg.no_blocks", default="(no log lines found)")

    if mode == "index":
        toc_lines = []
        for b in builder.blocks:
            b_num = b["block_num"]
            sum_str = b["summary"]
            toc_lines.append(f"Block {b_num:3d}: {sum_str}")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total blocks: {total}\n"
                "To retrieve lines, call log2idx with mode='section' and section=N."
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
        snippet_lines = []
        for l_num in range(target["start_line"] - 1, target["end_line"]):
            snippet_lines.append(f"{l_num + 1:5d} | {builder.lines[l_num]}")

        return f"=== Block {section_num} ({target['summary']}) ===\n" + "\n".join(
            snippet_lines
        )

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
