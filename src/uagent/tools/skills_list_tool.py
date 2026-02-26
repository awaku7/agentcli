# tools/skills_list_tool.py
"""skills_list_tool implementation for scanning Agent Skills."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import (
    get_default_skill_roots,
    load_skill_frontmatter_only,
    skill_md_path,
    validate_skill_frontmatter,
)

STATUS_LABEL = "tool:skills_list"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_list",
        "description": _(
            "tool.description",
            default="Returns a list of skills under the specified root (reads frontmatter only) based on Agent Skills spec (SKILL.md). Scans UAGENT_SKILLS_DIRS or ./skills if root_dir is omitted.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "root_dir": {
                    "type": "string",
                    "description": _(
                        "param.root_dir.description",
                        default="Root directory for skill search. Uses UAGENT_SKILLS_DIRS (os.pathsep delimited) or ./skills by default.",
                    ),
                },
                "recursive": {
                    "type": "boolean",
                    "description": _(
                        "param.recursive.description",
                        default="Whether to search recursively (default: true).",
                    ),
                    "default": True,
                },
                "include_invalid": {
                    "type": "boolean",
                    "description": _(
                        "param.include_invalid.description",
                        default="Whether to include skills that failed parsing or validation (default: true).",
                    ),
                    "default": True,
                },
                "strict": {
                    "type": "boolean",
                    "description": _(
                        "param.strict.description",
                        default="Whether to treat validation warnings as errors (default: false).",
                    ),
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _iter_candidate_skill_dirs(root_dir: str, recursive: bool) -> List[str]:
    out: List[str] = []
    root_dir = os.path.abspath(root_dir)

    if not os.path.isdir(root_dir):
        return out

    if recursive:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            base = os.path.basename(dirpath)
            if base in (".git", "node_modules", "__pycache__", ".venv", "venv"):
                dirnames[:] = []
                continue

            if "SKILL.md" in filenames:
                out.append(dirpath)
    else:
        for entry in os.scandir(root_dir):
            if not entry.is_dir():
                continue
            if os.path.isfile(os.path.join(entry.path, "SKILL.md")):
                out.append(entry.path)

    return out


def run_tool(args: Dict[str, Any]) -> str:
    root_dir = (args or {}).get("root_dir")
    recursive = bool((args or {}).get("recursive", True))
    include_invalid = bool((args or {}).get("include_invalid", True))
    strict = bool((args or {}).get("strict", False))

    roots: List[str]
    if isinstance(root_dir, str) and root_dir.strip():
        roots = [root_dir.strip()]
    else:
        roots = get_default_skill_roots()

    results: List[Dict[str, Any]] = []

    for r in roots:
        for skill_dir in _iter_candidate_skill_dirs(r, recursive=recursive):
            item: Dict[str, Any] = {
                "root": os.path.abspath(r),
                "path": os.path.abspath(skill_dir),
                "skill_md": os.path.abspath(skill_md_path(skill_dir)),
                "name": None,
                "description": None,
                "license": None,
                "compatibility": None,
                "metadata": None,
                "allowed_tools": None,
                "ok": False,
                "errors": [],
                "warnings": [],
            }

            try:
                fm = load_skill_frontmatter_only(skill_dir)
                item["name"] = fm.get("name")
                item["description"] = fm.get("description")
                item["license"] = fm.get("license")
                item["compatibility"] = fm.get("compatibility")
                item["metadata"] = fm.get("metadata")
                item["allowed_tools"] = fm.get("allowed-tools")

                ok, errors, warnings = validate_skill_frontmatter(
                    skill_dir, fm, strict=strict
                )
                item["ok"] = ok
                item["errors"] = errors
                item["warnings"] = warnings

            except Exception as e:
                item["ok"] = False
                item["errors"] = [f"Failed to load/parse frontmatter: {e!r}"]

            if item["ok"] or include_invalid:
                results.append(item)

    results.sort(key=lambda x: (x.get("name") or "", x.get("path") or ""))

    return json.dumps(results, ensure_ascii=False, indent=2)
