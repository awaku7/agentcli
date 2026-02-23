# tools/skills_validate_tool.py
"""skills_validate_tool

Validate a skill directory according to Agent Skills specification.
https://agentskills.io/specification

"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import (  # noqa: E402
    load_skill_frontmatter_only,
    skill_md_path,
    validate_skill_frontmatter,
)

STATUS_LABEL = "tool:skills_validate"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_validate",
        "description": "Agent Skills 仕様に従ってスキルディレクトリ（SKILL.md）を検証し、errors/warnings を返します。",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_dir": {
                    "type": "string",
                    "description": "スキルディレクトリ（直下に SKILL.md が必要）",
                },
                "strict": {
                    "type": "boolean",
                    "description": "warnings も失敗扱いにするか（既定:false）",
                    "default": False,
                },
            },
            "required": ["skill_dir"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return "[tool error] invalid args"

    skill_dir = args.get("skill_dir")
    strict = bool(args.get("strict", False))

    if not isinstance(skill_dir, str) or not skill_dir.strip():
        return "[tool error] skill_dir must be a non-empty string"

    skill_dir = skill_dir.strip()
    skill_md = skill_md_path(skill_dir)
    if not os.path.isfile(skill_md):
        out = {
            "ok": False,
            "errors": [f"SKILL.md not found: {os.path.abspath(skill_md)}"],
            "warnings": [],
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    try:
        fm = load_skill_frontmatter_only(skill_dir)
    except Exception as e:
        out = {
            "ok": False,
            "errors": [f"Failed to parse SKILL.md frontmatter: {e!r}"],
            "warnings": [],
        }
        return json.dumps(out, ensure_ascii=False, indent=2)

    ok, errors, warnings = validate_skill_frontmatter(skill_dir, fm, strict=strict)
    out = {"ok": ok, "errors": errors, "warnings": warnings}
    return json.dumps(out, ensure_ascii=False, indent=2)
