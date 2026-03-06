# tools/skills_load_tool.py
"""skills_load_tool implementation for Agent Skills."""

from __future__ import annotations

import json
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import load_skill_doc

STATUS_LABEL = "tool:skills_load"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_load",
        "description": _(
            "tool.description",
            default="Loads the SKILL.md for an Agent Skill and returns its YAML frontmatter and Markdown body.",
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
                }
            },
            "required": ["skill_dir"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return _("err.invalid_args", default="[tool error] invalid args")

    skill_dir = args.get("skill_dir")
    if not isinstance(skill_dir, str) or not skill_dir.strip():
        return _(
            "err.skill_dir_required",
            default="[tool error] skill_dir must be a non-empty string",
        )

    doc = load_skill_doc(skill_dir.strip())
    out = {
        "path": doc.path,
        "frontmatter": doc.frontmatter,
        "body_markdown": doc.body_markdown,
    }
    return json.dumps(out, ensure_ascii=False, indent=2)
