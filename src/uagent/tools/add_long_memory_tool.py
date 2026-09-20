# tools/add_long_memory_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any

from . import long_memory

BUSY_LABEL = False


TOOL_SPEC: dict[str, Any] = {
    "load_order": 7000,
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "add_long_memory",
        "description": _(
            "tool.description",
            default=(
                "Save a single long-term memory note about the user/environment that may be useful in future conversations."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "add_long_memory",
                "add long memory",
                "save note",
                "remember",
                "memory note",
                "long term memory",
            ],
        ),
        "x_search_terms_en": [
            "add_long_memory",
            "add long memory",
            "save note",
            "remember",
            "memory note",
            "long term memory",
        ],
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "note": {
                    "type": "string",
                    "description": _(
                        "param.note.description",
                        default=(
                            "Write exactly one concise note (Japanese preferred) that should be reusable in future conversations."
                        ),
                    ),
                },
                "owner": {
                    "type": "string",
                    "description": "Explicit memory owner boundary (optional).",
                },
                "project": {
                    "type": "string",
                    "description": "Explicit project boundary (optional).",
                },
            },
            "required": ["note"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    note = (args.get("note") or "").strip()
    if not note:
        return _("err.note_empty", default="[add_long_memory error] note is empty")

    owner = str(args.get("owner") or "").strip()
    project = str(args.get("project") or "").strip()
    if owner or project:
        saved = long_memory.append_long_memory(note, owner=owner, project=project)
    else:
        saved = long_memory.append_long_memory(note)
    if not saved:
        return _(
            "err.save",
            default="[add_long_memory error] failed to save memory",
        )
    return "[add_long_memory] saved"
