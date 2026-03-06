# tools/skills_validate_tool.py
"""skills_validate_tool implementation for Agent Skills."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import (
    load_skill_frontmatter_only,
    skill_md_path,
    validate_skill_frontmatter,
)

STATUS_LABEL = "tool:skills_validate"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_validate",
        "description": _(
            "tool.description",
            default="Validates a skill directory (SKILL.md) according to the Agent Skills spec and returns errors and warnings.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_dir": {
                    "type": "string",
                    "description": _(
                        "param.skill_dir.description",
                        default="The skill directory (must contain SKILL.md).",
                    ),
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
            "required": ["skill_dir"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return _("err.invalid_args", default="[tool error] invalid args")

    skill_dir = args.get("skill_dir")
    strict = bool(args.get("strict", False))

    if not isinstance(skill_dir, str) or not skill_dir.strip():
        return _(
            "err.skill_dir_required",
            default="[tool error] skill_dir must be a non-empty string",
        )

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
