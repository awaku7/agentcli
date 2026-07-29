from __future__ import annotations

import os
import json
from typing import Any, List, Dict

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "json2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a JSON file (.json) into key paths, array counts, and structural summaries, "
                "returning a numbered index or a specific section. Use this when reading large JSON files: "
                "call with mode='index' to get key paths and node summaries, then call with "
                "mode='section' and section=N to retrieve the content of that node."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read json file",
                "json index",
                "json parser",
                "json section",
                "JSONファイルを読む",
                "JSONインデックス",
                "キーパス表示",
                "セクション分割",
            ],
        ),
        "x_search_terms_en": [
            "read json file",
            "json index",
            "json parser",
            "json section",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the JSON file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents with JSONPath keys. '
                            '"section" returns the formatted JSON snippet of a specific node.'
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
                "max_depth": {
                    "type": "integer",
                    "description": _(
                        "param.max_depth.description",
                        default="Maximum nesting depth of key paths to include in the index (default 3).",
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}


class _JsonIndexBuilder:
    def __init__(self, data: Any, max_depth: int = 3):
        self.data = data
        self.max_depth = max_depth
        self.entries: List[Dict[str, Any]] = []
        self._walk(data, "$", depth=1)

    def _walk(self, node: Any, path: str, depth: int) -> None:
        if depth > self.max_depth:
            return

        if isinstance(node, dict):
            summary = f"dict ({len(node)} keys)"
            self.entries.append({"path": path, "summary": summary, "value": node})
            for k, v in node.items():
                child_path = f"{path}.{k}"
                self._walk(v, child_path, depth + 1)
        elif isinstance(node, list):
            summary = f"list ({len(node)} items)"
            self.entries.append({"path": path, "summary": summary, "value": node})
            for idx, item in enumerate(node[:10]):  # Sample first 10
                child_path = f"{path}[{idx}]"
                if isinstance(item, (dict, list)):
                    self._walk(item, child_path, depth + 1)


def run_tool(args: dict[str, Any]) -> str:
    path = args.get("path")
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")

    mode = args.get("mode", "index")
    section = args.get("section")
    max_depth = args.get("max_depth", 3)

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
        data = json.loads(source)
    except Exception as e:
        return _("err.parse_error", default="Error parsing JSON file: {e}").format(e=e)

    builder = _JsonIndexBuilder(data, max_depth=max_depth)

    if not builder.entries:
        return _("msg.no_entries", default="(no structural JSON nodes found)")

    if mode == "index":
        toc_lines = []
        for idx, entry in enumerate(builder.entries, 1):
            p_str = entry["path"]
            s_str = entry["summary"]
            toc_lines.append(f"{idx:3d}: {p_str} [{s_str}]")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total sections: {total}\n"
                "To retrieve a node, call json2idx with mode='section' and section=N."
            ),
        ).format(path=path, toc=toc, total=len(builder.entries))

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

        if section_num < 1 or section_num > len(builder.entries):
            return _(
                "err.section_not_found",
                default="Error: Section {section_num} not found. Valid range: 1..{last}.",
            ).format(section_num=section_num, last=len(builder.entries))

        target = builder.entries[section_num - 1]
        formatted = json.dumps(target["value"], indent=2, ensure_ascii=False)
        lines = formatted.splitlines()
        if len(lines) > 200:
            formatted = (
                "\n".join(lines[:200]) + f"\n... ({len(lines) - 200} lines truncated)"
            )

        return f"=== Node: {target['path']} ({target['summary']}) ===\n" + formatted

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
