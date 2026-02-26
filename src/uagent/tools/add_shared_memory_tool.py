# tools/add_shared_memory_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any, Dict

from . import shared_memory

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_shared_memory",
        "description": _(
            "tool.description",
            default=(
                "Append a single note to the shared long-term memory store (shared across users/sessions). "
                "If shared memory is not configured, the tool reports that it is disabled. "
                "Never store secrets such as passwords or API keys."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "Append exactly one note to the shared memory store.\n"
                "If shared memory is disabled (UAGENT_SHARED_MEMORY_FILE not set), return a message explaining how to enable it.\n"
                "Do not store secrets (passwords/tokens/API keys)."
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
                            "The note text to share. Use this for project-wide assumptions/policies that should be reused across sessions."
                        ),
                    ),
                }
            },
            "required": ["note"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    note = str(args.get("note", "")).strip()
    if not note:
        return "[add_shared_memory] nothing saved (note was empty)"

    if not shared_memory.is_enabled():
        return (
            "[add_shared_memory] shared memory is disabled (UAGENT_SHARED_MEMORY_FILE is not set).\n"
            "Set UAGENT_SHARED_MEMORY_FILE to enable shared memory."
        )

    try:
        shared_memory.append_shared_memory(note)
    except Exception as e:
        return (
            "[add_shared_memory] failed to write shared memory.\n"
            f"type={type(e).__name__}, error={e}"
        )

    return "[add_shared_memory] appended 1 note"
