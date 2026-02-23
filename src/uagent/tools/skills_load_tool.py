# tools/skills_load_tool.py
"""skills_load_tool

Load full SKILL.md (frontmatter + markdown body).

Agent Skills spec:
https://agentskills.io/specification

"""

from __future__ import annotations

import json
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import load_skill_doc  # noqa: E402

STATUS_LABEL = "tool:skills_load"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_load",
        "description": "Agent Skills の SKILL.md を読み込み、YAML frontmatter と Markdown本文(body)を返します。",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_dir": {
                    "type": "string",
                    "description": "スキルディレクトリ（直下に SKILL.md が必要）",
                }
            },
            "required": ["skill_dir"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return "[tool error] invalid args"

    skill_dir = args.get("skill_dir")
    if not isinstance(skill_dir, str) or not skill_dir.strip():
        return "[tool error] skill_dir must be a non-empty string"

    doc = load_skill_doc(skill_dir.strip())
    out = {
        "path": doc.path,
        "frontmatter": doc.frontmatter,
        "body_markdown": doc.body_markdown,
    }
    return json.dumps(out, ensure_ascii=False, indent=2)
