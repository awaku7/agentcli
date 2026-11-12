# tools/update_long_memory_tool.py

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
    "load_order": 7001,
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "update_long_memory",
        "description": _(
            "tool.description",
            default=(
                "Replace the text of one saved long-term memory note, addressed by its memory_id (see get_long_memory). "
                "Use this when the user corrects or updates something you previously saved, instead of adding a second, conflicting note."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "update_long_memory",
                "update long memory",
                "edit memory",
                "correct memory",
                "memory note",
                "long term memory",
            ],
        ),
        "x_search_terms_en": [
            "update_long_memory",
            "update long memory",
            "edit memory",
            "correct memory",
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
                        default="The memory_id of the note to replace, as returned by get_long_memory or add_long_memory.",
                    ),
                },
                "note": {
                    "type": "string",
                    "description": _(
                        "param.note.description",
                        default="The full replacement text for the note (one concise note, Japanese preferred).",
                    ),
                },
            },
            "required": ["memory_id", "note"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    memory_id = str(args.get("memory_id") or "").strip()
    note = (args.get("note") or "").strip()
    if not memory_id:
        return _(
            "err.memory_id_empty",
            default="[update_long_memory error] memory_id is empty",
        )
    if not note:
        return _("err.note_empty", default="[update_long_memory error] note is empty")
    result = long_memory.update_long_memory_by_id(memory_id, note)
    if result["saved"]:
        return _(
            "result.updated",
            default="[update_long_memory] updated (memory_id: %(memory_id)s)",
            memory_id=result["memory_id"],
        )
    if result["reason"] == "not_found":
        return _(
            "err.not_found",
            default="[update_long_memory error] no active memory with that memory_id",
        )
    if result["reason"] == "secret":
        return _(
            "err.secret",
            default=(
                "[update_long_memory error] note looks like it contains a "
                "credential; credentials must not be stored in memory"
            ),
        )
    if result["reason"] == "too_long":
        return _(
            "err.too_long",
            default="[update_long_memory error] note is too long; keep it to one concise note",
        )
    return _(
        "err.save",
        default="[update_long_memory error] failed to update memory",
    )


def describe(args: dict[str, Any]) -> str:
    """Localized pre-execution action line for UAGENT_SHOW_TOOL_RESULTS=2."""
    note = " ".join(str((args or {}).get("note") or "").split())
    if len(note) > 80:
        note = note[:79] + "…"
    if note:
        return _(
            "describe.update_with_note",
            default="Updating long-term memory: %(note)s",
            note=note,
        )
    return _("describe.update", default="Updating long-term memory")


TOOL_DESCRIBER = describe
