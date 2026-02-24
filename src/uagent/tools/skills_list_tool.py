# tools/skills_list_tool.py
"""skills_list_tool

Agent Skills spec:
https://agentskills.io/specification

This tool lists available skills by scanning a root directory for skill folders
that contain SKILL.md, and reading YAML frontmatter only (progressive disclosure).

Default roots policy:
- If root_dir is provided (non-empty), use it.
- Otherwise, use env var UAGENT_SKILLS_DIRS split by os.pathsep
- If env var is not set, fallback to ./skills

"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import (  # noqa: E402
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
        "description": "Agent Skills 仕様(SKILL.md)に基づき、指定ルート配下のスキル一覧を返します（frontmatterのみ読み込み）。root_dir未指定時は環境変数UAGENT_SKILLS_DIRS、無ければ./skillsを探索します。",
        "parameters": {
            "type": "object",
            "properties": {
                "root_dir": {
                    "type": "string",
                    "description": "スキル探索ルート。空/未指定なら UAGENT_SKILLS_DIRS (os.pathsep区切り) を使用し、未設定時は ./skills を使用します。",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "再帰的に探索するか（既定:true）",
                    "default": True,
                },
                "include_invalid": {
                    "type": "boolean",
                    "description": "SKILL.mdの解析/検証に失敗しても一覧へ含めるか（既定:true）。falseの場合、失敗スキルは除外します。",
                    "default": True,
                },
                "strict": {
                    "type": "boolean",
                    "description": "仕様検証で warnings を失敗扱いにするか（既定:false）",
                    "default": False,
                },
            },
            "required": [],
        },
    },
}


def _iter_candidate_skill_dirs(root_dir: str, recursive: bool) -> List[str]:
    """Return directories that contain SKILL.md under root_dir."""

    out: List[str] = []
    root_dir = os.path.abspath(root_dir)

    if not os.path.isdir(root_dir):
        return out

    if recursive:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Skip typical heavy dirs if someone points to a big tree.
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

    # Deterministic order
    results.sort(key=lambda x: (x.get("name") or "", x.get("path") or ""))

    return json.dumps(results, ensure_ascii=False, indent=2)
