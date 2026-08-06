from __future__ import annotations

import os
import re
from typing import Any

from .index_tool_helpers import read_index_source, resolve_index_path

TOOL_SPEC = {
    "type": "function",
    "tool_genre": "index",
    "function": {
        "name": "sln2idx",
        "description": "Parse Visual Studio .sln and .slnx solution files into a numbered index or a selected section.",
        "x_parallel_safe": True,
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to a .sln or .slnx file.",
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

_PROJECT = re.compile(
    r'^Project\("(?P<type>[^"]+)"\) = "(?P<name>[^"]+)", "(?P<path>[^"]+)", "(?P<guid>[^"]+)"'
)


def _sln_sections(source: str) -> list[tuple[str, str]]:
    projects = []
    configurations = []
    dependencies = []
    for line in source.splitlines():
        match = _PROJECT.match(line.strip())
        if match:
            projects.append(match.groupdict())
        if (
            "SolutionConfigurationPlatforms" in line
            or "ProjectConfigurationPlatforms" in line
        ):
            configurations.append(line.strip())
        if (
            "ProjectSection(ProjectDependencies)" in line
            or " = " in line
            and "ProjectSection" not in line
        ):
            if "ProjectDependencies" in line or line.strip().endswith(" ="):
                dependencies.append(line.strip())
    project_text = (
        "\n".join(
            f"  {p['name']} | {p['path']} | {p['guid']} | type={p['type']}"
            for p in projects
        )
        or "  (none)"
    )
    return [
        ("Projects", project_text),
        (
            "Solution configuration lines",
            "\n".join(f"  {line}" for line in configurations) or "  (none)",
        ),
        (
            "Dependencies / project sections",
            "\n".join(f"  {line}" for line in dependencies) or "  (none)",
        ),
    ]


def run_tool(args: dict[str, Any]) -> str:
    path = str(args.get("path", ""))
    if not path:
        return "Error: 'path' is required."
    try:
        safe = resolve_index_path(path)
        if not os.path.isfile(safe):
            raise FileNotFoundError(path)
        if os.path.splitext(safe)[1].lower() not in {".sln", ".slnx"}:
            raise ValueError("only .sln and .slnx files are supported")
        source = read_index_source(safe)
        if "<!DOCTYPE" in source.upper() or "<!ENTITY" in source.upper():
            raise ValueError("DTD and external entities are not allowed")
        sections = _sln_sections(source)
    except Exception as exc:
        return f"Error parsing solution: {exc}"
    if args.get("mode", "index") == "section":
        try:
            number = int(args.get("section"))
        except (TypeError, ValueError):
            return "Error: 'section' must be an integer."
        if number < 1 or number > len(sections):
            return f"Error: section must be between 1 and {len(sections)}."
        label, body = sections[number - 1]
        return f"Section {number}: {label}\n---\n{body}"
    lines = [f"Solution: {path}", "---"]
    for index, (label, body) in enumerate(sections, 1):
        lines.append(f"{index}. {label} ({len(body.splitlines())} entries)")
    lines += ["---", f"Total sections: {len(sections)}"]
    return "\n".join(lines)
