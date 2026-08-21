# tools/skills_load_tool.py
"""skills_load_tool implementation for Agent Skills."""

from __future__ import annotations

import json
import re
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import load_skill_doc

STATUS_LABEL = "tool:skills_load"

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "skills_load",
        "description": _(
            "tool.description",
            default="Loads the SKILL.md for an Agent Skill and returns its YAML frontmatter and Markdown body.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "skills_load",
                "skills load",
                "agent skill",
                "skill management",
                "skill file",
                "SKILL.md",
            ],
        ),
        "x_search_terms_en": [
            "skills_load",
            "skills load",
            "agent skill",
            "skill management",
            "skill file",
            "SKILL.md",
        ],
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


def run_tool(args: dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return _("err.invalid_args", default="[tool error] invalid args")

    skill_dir = args.get("skill_dir")
    if not isinstance(skill_dir, str) or not skill_dir.strip():
        return _(
            "err.skill_dir_required",
            default="[tool error] skill_dir must be a non-empty string",
        )

    doc = load_skill_doc(skill_dir.strip())

    # skills_load is also callable directly by the LLM (not only through the
    # :skills command). Pin the tools declared by the loaded skill here so the
    # round-loop auto-unloader cannot remove them before skill execution ends.
    try:
        from .skill_history import pin_skill_tools

        allowed_tools = doc.frontmatter.get("allowed-tools")
        pin_skill_tools(allowed_tools)

        # Load every tool explicitly declared by the skill.  This is needed
        # for direct LLM calls to skills_load; the :skills command only
        # preloads the core skill-management tools.
        if isinstance(allowed_tools, str):
            from ._genre_control_util import enable_single_tool

            management_tools = {"tool_catalog", "tool_load", "unload_tool"}
            for tool_name in re.split(r"[\s,]+", allowed_tools.strip()):
                if tool_name and tool_name not in management_tools:
                    try:
                        enable_single_tool(tool_name)
                    except Exception:
                        pass
    except Exception:
        # Loading a skill must remain usable even if optional pinning/loading fails.
        pass

    out = {
        "path": doc.path,
        "frontmatter": doc.frontmatter,
        "body_markdown": doc.body_markdown,
    }
    return json.dumps(out, ensure_ascii=False, indent=2)
