from __future__ import annotations

import os
from typing import Any, List, Dict

import yaml

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "yaml2idx",
        "description": _(
            "tool.description",
            default=(
                "Parse a YAML file into key paths, document blocks, and structural summaries, "
                "returning a numbered index or a specific section. Use this when reading large YAML, "
                "Kubernetes manifests, Docker Compose, OpenAPI, or GitHub Actions files: call with "
                "mode='index' to get the table of contents with JSONPath-style key paths, then call with "
                "mode='section' and the section number to retrieve only the required lines."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "read yaml file",
                "yaml file index",
                "yaml parser",
                "yaml section",
                "kubernetes manifest reader",
                "docker compose index",
                "openapi reader",
                "Read YAML files",
                "YAML index",
                "Display key paths",
                "K8s manifest analysis",
                "Split into sections",
            ],
        ),
        "x_search_terms_en": [
            "read yaml file",
            "yaml file index",
            "yaml parser",
            "yaml section",
            "kubernetes manifest reader",
            "docker compose index",
            "openapi reader",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the YAML file.",
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default=(
                            '"index" returns a numbered table of contents with line numbers and key paths. '
                            '"section" returns a specific definition section by number.'
                        ),
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default=(
                            "Section number to retrieve (used only when mode='section'). "
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


class _YamlIndexBuilder:
    def __init__(self, source: str, filepath: str = "", max_depth: int = 3):
        self.source = source
        self.filepath = filepath
        self.lines = source.split("\n")
        self.max_depth = max_depth
        self.entries: List[Dict[str, Any]] = []
        self._parse()

    def _detect_summary(self, node: yaml.MappingNode) -> str:
        m = {}
        for k, v in node.value:
            if isinstance(k, yaml.ScalarNode):
                m[k.value] = v

        if "kind" in m and isinstance(m["kind"], yaml.ScalarNode):
            kind_val = m["kind"].value
            name_val = ""
            if "metadata" in m and isinstance(m["metadata"], yaml.MappingNode):
                meta_map = {
                    k.value: v
                    for k, v in m["metadata"].value
                    if isinstance(k, yaml.ScalarNode)
                }
                if "name" in meta_map and isinstance(meta_map["name"], yaml.ScalarNode):
                    name_val = meta_map["name"].value
            return f"kind: {kind_val}" + (
                f" (metadata.name: {name_val})" if name_val else ""
            )
        if "services" in m:
            return "Docker Compose"
        if "openapi" in m and isinstance(m["openapi"], yaml.ScalarNode):
            return f"OpenAPI {m['openapi'].value}"
        if "jobs" in m:
            return "GitHub Actions Workflow"
        return ""

    def _parse(self) -> None:
        try:
            nodes = list(yaml.compose_all(self.source))
        except Exception:
            # Fallback line scanner for invalid/unparsable YAML
            self._parse_fallback()
            return

        total_docs = len(nodes)
        for doc_idx, node in enumerate(nodes, 1):
            if node is None:
                continue
            doc_start = node.start_mark.line + 1
            doc_end = node.end_mark.line + 1

            summary = ""
            if isinstance(node, yaml.MappingNode):
                summary = self._detect_summary(node)

            if total_docs > 1 or summary:
                label = f"Doc #{doc_idx}"
                if summary:
                    label += f" [{summary}]"
                self.entries.append(
                    {
                        "type": "doc",
                        "path": label,
                        "start_line": doc_start,
                        "end_line": doc_end,
                    }
                )

            prefix_base = f"Doc #{doc_idx}" if total_docs > 1 else ""
            if isinstance(node, yaml.Node):
                self._walk_node(node, prefix_base, depth=1)

    def _walk_node(self, node: yaml.Node, prefix: str, depth: int) -> None:
        if depth > self.max_depth:
            return

        if isinstance(node, yaml.MappingNode):
            for k_node, v_node in node.value:
                if not isinstance(k_node, yaml.ScalarNode):
                    continue
                k_str = k_node.value
                current_path = f"{prefix}.{k_str}" if prefix else k_str
                start_line = k_node.start_mark.line + 1
                end_line = v_node.end_mark.line + 1

                self.entries.append(
                    {
                        "type": "key",
                        "path": current_path,
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )

                if isinstance(v_node, yaml.MappingNode):
                    self._walk_node(v_node, current_path, depth + 1)
                elif isinstance(v_node, yaml.SequenceNode):
                    for item_idx, item_node in enumerate(v_node.value):
                        if isinstance(item_node, yaml.MappingNode):
                            item_prefix = f"{current_path}[{item_idx}]"
                            self._walk_node(item_node, item_prefix, depth + 1)

    def _parse_fallback(self) -> None:
        for idx, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                if ":" in stripped:
                    key = stripped.split(":", 1)[0].strip()
                    self.entries.append(
                        {
                            "type": "key",
                            "path": key,
                            "start_line": idx,
                            "end_line": idx,
                        }
                    )


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
    except Exception as e:
        return _("err.read_error", default="Error reading file: {e}").format(e=e)

    try:
        builder = _YamlIndexBuilder(source, filepath=path, max_depth=max_depth)
    except Exception as e:
        return _("err.parse_error", default="Error parsing YAML file: {e}").format(e=e)

    if not builder.entries:
        return _("msg.no_entries", default="(no structural YAML keys found)")

    lines = source.split("\n")

    if mode == "index":
        toc_lines = []
        for idx, entry in enumerate(builder.entries, 1):
            path_str = entry["path"]
            s_line = entry["start_line"]
            e_line = entry["end_line"]
            toc_lines.append(f"{idx:3d}: {path_str} (lines {s_line}-{e_line})")

        toc = "\n".join(toc_lines)
        return _(
            "msg.index_output",
            default=(
                "Index for: {path}\n---\n{toc}\n---\n"
                "Total sections: {total}\n"
                "To retrieve a section, call yaml2idx with mode='section' and section=N."
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
        start_idx = max(0, target["start_line"] - 1)
        end_idx = min(len(lines), target["end_line"])

        snippet_lines = []
        for l_num in range(start_idx, end_idx):
            snippet_lines.append(f"{l_num + 1:4d} | {lines[l_num]}")

        return "\n".join(snippet_lines)

    else:
        return _(
            "err.invalid_mode",
            default="Error: Invalid mode '{mode}'. Use 'index' or 'section'.",
        ).format(mode=mode)
