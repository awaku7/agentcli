# tools/skills_read_file_tool.py
"""skills_read_file_tool implementation for Agent Skills."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from .agent_skills_shared import (
    DEFAULT_MAX_READ_FILE_BYTES,
    _read_text_file,
    safe_resolve_skill_relative_path,
)

STATUS_LABEL = "tool:skills_read_file"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "skills_read_file",
        "description": _(
            "tool.description",
            default="Safely reads a file under a skill directory using a relative path. Path traversal is blocked.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_dir": {
                    "type": "string",
                    "description": _("param.skill_dir.description", default="The skill directory."),
                },
                "relative_path": {
                    "type": "string",
                    "description": _(
                        "param.relative_path.description",
                        default="The relative path from the skill root (e.g., references/REFERENCE.md).",
                    ),
                },
                "max_bytes": {
                    "type": "integer",
                    "description": _(
                        "param.max_bytes.description",
                        default="Maximum number of bytes to read (default: 5,000,000).",
                    ),
                    "default": DEFAULT_MAX_READ_FILE_BYTES,
                },
            },
            "required": ["skill_dir", "relative_path"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return "[tool error] invalid args"

    skill_dir = args.get("skill_dir")
    relative_path = args.get("relative_path")
    max_bytes = args.get("max_bytes", DEFAULT_MAX_READ_FILE_BYTES)

    if not isinstance(skill_dir, str) or not skill_dir.strip():
        return "[tool error] skill_dir must be a non-empty string"
    if not isinstance(relative_path, str) or not relative_path.strip():
        return "[tool error] relative_path must be a non-empty string"
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        return "[tool error] max_bytes must be a positive integer"

    skill_dir = skill_dir.strip()
    relative_path = relative_path.strip()

    resolved = safe_resolve_skill_relative_path(skill_dir, relative_path)
    if not os.path.isfile(resolved):
        return json.dumps(
            {"ok": False, "error": f"File not found: {resolved}", "path": resolved},
            ensure_ascii=False,
            indent=2,
        )

    content = _read_text_file(resolved, max_bytes=max_bytes)
    return json.dumps(
        {"ok": True, "path": resolved, "content": content}, ensure_ascii=False, indent=2
    )
