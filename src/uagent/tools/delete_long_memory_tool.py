# tools/delete_long_memory_tool.py

from __future__ import annotations

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any

from . import long_memory

BUSY_LABEL = False


def is_loadable() -> bool:
    """UAGENT_MEMORY_TOOL_SAVE=0 opts out of agent-managed memory writes."""
    return long_memory.tool_save_enabled()


TOOL_SPEC: dict[str, Any] = {
    "load_order": 7002,
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "delete_long_memory",
        "description": _(
            "tool.description",
            default=(
                "Forget one saved long-term memory note, addressed by its memory_id (see get_long_memory). "
                "The note is tombstoned: it stops being used immediately but can be restored from :mem if it was deleted by mistake. "
                "Use this when the user asks you to forget something, or when a saved note is no longer true and should not be replaced."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "delete_long_memory",
                "delete long memory",
                "forget memory",
                "remove memory",
                "memory note",
                "long term memory",
            ],
        ),
        "x_search_terms_en": [
            "delete_long_memory",
            "delete long memory",
            "forget memory",
            "remove memory",
            "memory note",
            "long term memory",
        ],
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": _(
                        "param.memory_id.description",
                        default="The memory_id of the note to forget, as returned by get_long_memory or add_long_memory.",
                    ),
                },
            },
            "required": ["memory_id"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    memory_id = str(args.get("memory_id") or "").strip()
    if not memory_id:
        return _(
            "err.memory_id_empty",
            default="[delete_long_memory error] memory_id is empty",
        )
    target = long_memory.find_long_memory_by_id(memory_id)
    if target is None:
        return _(
            "err.not_found",
            default="[delete_long_memory error] no active memory with that memory_id",
        )
    if not long_memory.delete_long_memory_by_id(memory_id):
        return _(
            "err.delete",
            default="[delete_long_memory error] failed to delete memory",
        )
    return _(
        "result.deleted",
        default="[delete_long_memory] forgotten (memory_id: %(memory_id)s)",
        memory_id=memory_id,
    )


def describe(args: dict[str, Any]) -> str:
    """Localized pre-execution action line for UAGENT_SHOW_TOOL_RESULTS=2."""
    memory_id = str((args or {}).get("memory_id") or "").strip()
    if memory_id:
        return _(
            "describe.delete_with_id",
            default="Forgetting long-term memory %(memory_id)s",
            memory_id=memory_id,
        )
    return _("describe.delete", default="Forgetting long-term memory")


TOOL_DESCRIBER = describe
