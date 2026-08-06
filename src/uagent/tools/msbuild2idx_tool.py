from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Any

from .i18n_helper import make_tool_translator
from .index_tool_helpers import read_index_source, resolve_index_path

_ = make_tool_translator(__file__)

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "msbuild2idx",
        "description": "Parse MSBuild XML project files such as .csproj, .fsproj, .vbproj, .vcxproj, .props, and .targets into a numbered index or a selected section.",
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to an MSBuild XML file.",
                },
                "mode": {"type": "string", "enum": ["index", "section"]},
                "section": {
                    "type": "integer",
                    "description": "Section number for section mode.",
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}

_SUPPORTED = {
    ".csproj",
    ".fsproj",
    ".vbproj",
    ".vcxproj",
    ".props",
    ".targets",
    ".sqlproj",
    ".wixproj",
    ".shproj",
    ".esproj",
}
_MAX_BYTES = 20_000_000


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse(path: str) -> tuple[ET.Element, str]:
    if os.path.splitext(path)[1].lower() not in _SUPPORTED:
        raise ValueError(f"unsupported MSBuild extension: {os.path.splitext(path)[1]}")
    if os.path.getsize(path) > _MAX_BYTES:
        raise ValueError("file is too large")
    source = read_index_source(path)
    if "<!DOCTYPE" in source.upper() or "<!ENTITY" in source.upper():
        raise ValueError("DTD and external entities are not allowed")
    return ET.fromstring(source), source


def _sections(root: ET.Element) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for child in root:
        tag = _local(child.tag)
        if tag in {"PropertyGroup", "ItemGroup", "ImportGroup", "Target", "Choose"}:
            condition = child.attrib.get("Condition")
            label = tag + (f" [Condition: {condition}]" if condition else "")
            lines = []
            for node in child:
                name = _local(node.tag)
                include = (
                    node.attrib.get("Include")
                    or node.attrib.get("Update")
                    or node.attrib.get("Remove")
                )
                value = (node.text or "").strip()
                detail = name
                if include:
                    detail += f" Include={include}"
                if value:
                    detail += f" = {value}"
                lines.append(f"  {detail}")
            sections.append((label, "\n".join(lines) or "  (empty)"))
    return sections


def run_tool(args: dict[str, Any]) -> str:
    path = str(args.get("path", ""))
    if not path:
        return "Error: 'path' is required."
    try:
        safe = resolve_index_path(path)
        if not os.path.isfile(safe):
            raise FileNotFoundError(path)
        root, source = _parse(safe)
        sections = _sections(root)
    except Exception as exc:
        return f"Error parsing MSBuild file: {exc}"
    if args.get("mode", "index") == "section":
        try:
            number = int(args.get("section"))
        except (TypeError, ValueError):
            return "Error: 'section' must be an integer."
        if number < 1 or number > len(sections):
            return f"Error: section must be between 1 and {len(sections)}."
        label, body = sections[number - 1]
        return f"Section {number}: {label}\n---\n{body}"
    lines = [f"MSBuild project: {path}", "---"]
    lines.append(f"Root: {_local(root.tag)}")
    sdk = root.attrib.get("Sdk")
    if sdk:
        lines.append(f"SDK: {sdk}")
    lines.append(f"Bytes: {len(source.encode('utf-8'))}")
    for index, (label, body) in enumerate(sections, 1):
        lines.append(f"{index}. {label} ({len(body.splitlines())} entries)")
    lines.append("---")
    lines.append(f"Total sections: {len(sections)}")
    return "\n".join(lines)
