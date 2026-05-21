"""finish_skill_tool implementation to explicitly end a skill session."""

from __future__ import annotations

import json
from typing import Any, Dict

from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

STATUS_LABEL = "tool:finish_skill"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "finish_skill",
        "description": _(
            "tool.description",
            default="Signal that the current skill's tasks are complete. (Use ONLY during skill execution based on SKILL.md). This removes skill instructions and prevents infinite loops.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "finish_skill",
                "finish skill",
                "complete skill",
                "end skill",
                "skill done",
                "mark done",
                "signal complete",
                "finish task",
                "stop instructions",
                "end loop",
            ],
        ),
        "x_search_terms_en": [
            "finish_skill",
            "finish skill",
            "complete skill",
            "end skill",
            "skill done",
            "mark done",
            "signal complete",
            "finish task",
            "stop instructions",
            "end loop",
        ],
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
    message = (args or {}).get("message") or "Skill execution finished."

    cb = get_callbacks().finish_skill
    if cb is not None:
        try:
            return cb(message)
        except Exception:
            pass

    return json.dumps({"status": "ok", "message": message}, ensure_ascii=False)
