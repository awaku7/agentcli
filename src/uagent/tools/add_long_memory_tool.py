# tools/add_long_memory_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict

from . import long_memory

BUSY_LABEL = False


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_long_memory",
        "description": _(
            "tool.description",
            default=(
                "Save a single long-term memory note about the user/environment that may be useful in future conversations."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Save one useful long-term memory note.\n"
                "Do not store secrets such as passwords, API keys, or tokens."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": _(
                        "param.note.description",
                        default=(
                            "Write exactly one concise note (Japanese preferred) that should be reusable in future conversations."
                        ),
                    ),
                }
            },
            "required": ["note"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    note = (args.get("note") or "").strip()
    if not note:
        return "[add_long_memory error] note is empty"

    long_memory.append_long_memory(note)
    return "[add_long_memory] saved"
