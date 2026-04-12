# tools/finish_skill_tool.py
"""finish_skill_tool implementation to explicitly end a skill session."""

from __future__ import annotations

import json
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:finish_skill"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "finish_skill",
        "description": _(
            "tool.description",
            default="Signal that the current skill's tasks are complete. This removes skill instructions and prevents infinite loops.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="Optional final message to the user.",
                    ),
                }
            },
            "required": [],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    # Note: The actual clearing logic is handled by the caller (session/CLI) 
    # when it detects this tool has been called, because it needs access 
    # to the message history reference.
    message = (args or {}).get("message") or "Skill execution finished."
    return json.dumps({"status": "ok", "message": message}, ensure_ascii=False)
