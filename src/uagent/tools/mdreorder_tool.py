from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _parse_markdown(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {
        "level": 0,
        "title": "",
        "heading_line": "",
        "body": [],
        "children": [],
    }
    stack = [root]
    for line in text.splitlines(keepends=True):
        m = _HEADING_RE.match(line.rstrip("\r\n"))
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            node: dict[str, Any] = {
                "level": level,
                "title": title,
                "heading_line": line.rstrip("\r\n"),
                "body": [],
                "children": [],
            }
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            stack[-1]["children"].append(node)
            stack.append(node)
        else:
            stack[-1]["body"].append(line)
    return root


def _serialize(node: dict[str, Any]) -> str:
    parts: list[str] = []
    if node.get("heading_line"):
        parts.append(node["heading_line"] + "\n")
    parts.extend(node.get("body", []))
    for child in node.get("children", []):
        parts.append(_serialize(child))
    return "".join(parts)


def _reorder_children(
    src_children: list[dict[str, Any]],
    ref_children: list[dict[str, Any]],
    drop_extras: bool,
) -> list[dict[str, Any]]:
    if not ref_children:
        return src_children

    ref_map: dict[str, list[int]] = {}
    for idx, child in enumerate(ref_children):
        ref_map.setdefault(_norm(child["title"]), []).append(idx)

    used: set[int] = set()
    reordered: list[dict[str, Any]] = []
    matched_any = False
    for ref_child in ref_children:
        key = _norm(ref_child["title"])
        match_idx = None
        for idx, src_child in enumerate(src_children):
            if idx in used:
                continue
            if _norm(src_child["title"]) == key:
                match_idx = idx
                break
        if match_idx is not None:
            used.add(match_idx)
            reordered.append(src_children[match_idx])
            matched_any = True

    if matched_any:
        if not drop_extras:
            reordered.extend(
                src_children[idx] for idx in range(len(src_children)) if idx not in used
            )
        return reordered

    # No title matches (common for translated docs): preserve source order
    # rather than truncating potentially valid sections.
    return src_children


def _reorder_tree(src: dict[str, Any], ref: dict[str, Any], drop_extras: bool) -> None:
    src_children = src.get("children", [])
    ref_children = ref.get("children", [])
    if not src_children or not ref_children:
        return

    new_children = _reorder_children(src_children, ref_children, drop_extras)
    src["children"] = new_children

    # Pair children recursively: prefer exact title matches, otherwise align by position.
    ref_by_title: dict[str, dict[str, Any]] = {}
    for child in ref_children:
        ref_by_title[_norm(child["title"])] = child

    for idx, child in enumerate(new_children):
        ref_child = ref_by_title.get(_norm(child["title"]))
        if ref_child is None and idx < len(ref_children):
            ref_child = ref_children[idx]
        if ref_child is not None:
            _reorder_tree(child, ref_child, drop_extras)


def run_tool(args: dict[str, Any]) -> str:
    """Reorder markdown sections to match a reference outline."""
    path_raw = str(args.get("path", "")).strip()
    if not path_raw:
        return _("err.path_required", default="Error: 'path' is required.")
    path = Path(path_raw)

    reference_path_raw = str(args.get("reference_path", "")).strip()
    reference_path = Path(reference_path_raw) if reference_path_raw else None
    output_path_raw = str(args.get("output_path", "")).strip()
    output_path = Path(output_path_raw) if output_path_raw else None
    drop_extras = bool(args.get("drop_extras", True))

    if not path.exists():
        return _(
            "err.file_not_found", default="Error: File not found: {path}", path=path
        )
    if reference_path is not None and not reference_path.exists():
        return _(
            "err.reference_not_found",
            default="Error: Reference file not found: {reference_path}",
            reference_path=reference_path,
        )

    source_text = path.read_text(encoding="utf-8")
    source_tree = _parse_markdown(source_text)

    ref_tree = (
        _parse_markdown(reference_path.read_text(encoding="utf-8"))
        if reference_path
        else source_tree
    )
    _reorder_tree(source_tree, ref_tree, drop_extras=drop_extras)

    result = _serialize(source_tree)
    if output_path is not None:
        output_path.write_text(result, encoding="utf-8")
        return json.dumps(
            {
                "ok": True,
                "input": str(path),
                "reference": str(reference_path) if reference_path else None,
                "output": str(output_path),
                "drop_extras": drop_extras,
            },
            ensure_ascii=False,
        )

    return result


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mdreorder_tool",
        "description": _(
            "tool.description",
            default="Markdownの見出し構成を参照ファイルに合わせて並べ替え、余分な章を削除できるツール",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["mdreorder_tool", "markdown reorder", "markdown sections"],
        ),
        "x_search_terms_en": [
            "mdreorder_tool",
            "markdown reorder",
            "markdown sections",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path",
                        default="Path to the Markdown file to reorder",
                    ),
                },
                "reference_path": {
                    "type": "string",
                    "description": _(
                        "param.reference_path",
                        default="Reference Markdown file used as the outline template",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path",
                        default="Optional output path; if omitted, returns the reordered text",
                    ),
                },
                "drop_extras": {
                    "type": "boolean",
                    "description": _(
                        "param.drop_extras",
                        default="Remove sections that do not exist in the reference outline",
                    ),
                    "default": True,
                },
            },
            "required": ["path"],
        },
    },
}
