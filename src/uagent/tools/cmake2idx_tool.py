from __future__ import annotations

import json
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
        "name": "cmake2idx",
        "description": _(
            "tool.description",
            default="Parse CMakeLists.txt, .cmake, and CMake preset files into a numbered index or selected section.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "CMake",
                "CMakeLists.txt",
                "cmake project",
                "CMake target",
                "CMake preset",
                "cmake parser",
            ],
        ),
        "x_search_terms_en": [
            "CMake",
            "CMakeLists.txt",
            "cmake project",
            "CMake target",
            "CMake preset",
            "cmake parser",
        ],
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description", default="Path to a CMake file."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["index", "section"],
                    "description": _(
                        "param.mode.description",
                        default='"index" returns a numbered table of contents; "section" returns one section.',
                    ),
                },
                "section": {
                    "type": "integer",
                    "description": _(
                        "param.section.description",
                        default="Section number for section mode.",
                    ),
                },
            },
            "required": ["path", "mode"],
            "additionalProperties": False,
        },
    },
}

_MAX_BYTES = 20_000_000
_COMMANDS = {
    "project",
    "cmake_minimum_required",
    "add_executable",
    "add_library",
    "target_sources",
    "target_include_directories",
    "target_link_libraries",
    "target_compile_definitions",
    "target_compile_options",
    "find_package",
    "add_subdirectory",
    "include",
    "option",
    "set",
    "install",
    "enable_testing",
    "add_test",
    "FetchContent_Declare",
    "ExternalProject_Add",
}
_CALL_RE = re.compile(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)", re.DOTALL)


def _parse_preset(path: str, source: str) -> list[tuple[str, str]]:
    data = json.loads(source)
    sections = []
    for key in ("configurePresets", "buildPresets", "testPresets", "workflowPresets"):
        values = data.get(key, [])
        if isinstance(values, list):
            body = (
                "\n".join(
                    f"  {item.get('name', '(unnamed)')}"
                    for item in values
                    if isinstance(item, dict)
                )
                or "  (none)"
            )
            sections.append((key, body))
    return sections


def _parse_cmake(source: str) -> list[tuple[str, str]]:
    sections: dict[str, list[str]] = {
        "Project metadata": [],
        "Targets": [],
        "Packages": [],
        "Directories": [],
        "Tests": [],
        "Other commands": [],
    }
    for match in _CALL_RE.finditer(source):
        command = match.group(1)
        body = " ".join(match.group(2).split())
        if command not in _COMMANDS:
            continue
        line = f"{command}({body})"
        if command in {"project", "cmake_minimum_required"}:
            group = "Project metadata"
        elif command.startswith("target_") or command in {
            "add_executable",
            "add_library",
        }:
            group = "Targets"
        elif command == "find_package":
            group = "Packages"
        elif command in {"add_subdirectory", "include"}:
            group = "Directories"
        elif command in {"add_test", "enable_testing"}:
            group = "Tests"
        else:
            group = "Other commands"
        sections[group].append(line)
    return [
        (key, "\n".join(f"  {line}" for line in values) or "  (none)")
        for key, values in sections.items()
    ]


def run_tool(args: dict[str, Any]) -> str:
    path = str(args.get("path", ""))
    if not path:
        return _("err.path_required", default="Error: 'path' is required.")
    try:
        safe = resolve_index_path(path)
        if not os.path.isfile(safe):
            raise FileNotFoundError(path)
        if os.path.getsize(safe) > _MAX_BYTES:
            raise ValueError("file is too large")
        source = read_index_source(safe)
        suffix = os.path.splitext(safe)[1].lower()
        if suffix in {".json"} and os.path.basename(safe).lower() in {
            "cmakepresets.json",
            "cmakeuserpresets.json",
        }:
            sections = _parse_preset(safe, source)
        else:
            sections = _parse_cmake(source)
    except Exception as exc:
        return _(
            "err.parse_error", default="Error parsing CMake file: {exc}", exc=str(exc)
        )
    if args.get("mode", "index") == "section":
        try:
            number = int(args.get("section"))
        except (TypeError, ValueError):
            return _(
                "err.section_invalid", default="Error: 'section' must be an integer."
            )
        if number < 1 or number > len(sections):
            return _(
                "err.section_not_found",
                default="Error: section must be between 1 and {total}.",
                total=len(sections),
            )
        label, body = sections[number - 1]
        return f"Section {number}: {label}\n---\n{body}"
    lines = [f"CMake file: {path}", "---"]
    for number, (label, body) in enumerate(sections, 1):
        lines.append(f"{number}. {label} ({len(body.splitlines())} entries)")
    lines.extend(["---", f"Total sections: {len(sections)}"])
    return "\n".join(lines)
