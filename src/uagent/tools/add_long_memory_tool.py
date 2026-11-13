# tools/add_long_memory_tool.py

from __future__ import annotations

from .i18n_helper import get_locale, make_tool_translator

_ = make_tool_translator(__file__)

from typing import Any

from . import long_memory

BUSY_LABEL = False


def is_loadable() -> bool:
    """UAGENT_MEMORY_TOOL_SAVE=0 opts out of agent-managed memory writes."""
    return long_memory.tool_save_enabled()


def _scope_description(kind: str) -> str:
    if get_locale() == "ja":
        if kind == "owner":
            return "メモリ所有者の明示的な境界（任意）。"
        return "明示的なプロジェクト境界（任意）。"
    if kind == "owner":
        return "Explicit memory owner boundary (optional)."
    return "Explicit project boundary (optional)."


TOOL_SPEC: dict[str, Any] = {
    "load_order": 7000,
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "add_long_memory",
        "description": _(
            "tool.description",
            default=(
                "Save a single long-term memory note about the user/environment that may be useful in future conversations. "
                "Save durable facts, preferences, constraints, decisions and commitments stated by the user; "
                "do not save one-off task details, guesses, or anything containing passwords, tokens or other credentials. "
                "If a similar note already exists, update it with update_long_memory instead of adding a duplicate."
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
                    "description": _scope_description("owner"),
                },
                "project": {
                    "type": "string",
                    "description": _scope_description("project"),
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
    result = long_memory.save_long_memory(
        note, owner=owner, project=project, source="tool"
    )
    if result["saved"]:
        return _(
            "result.saved",
            default="[add_long_memory] saved (memory_id: %(memory_id)s)",
            memory_id=result["memory_id"],
        )
    if result["reason"] == "duplicate":
        return _(
            "result.duplicate",
            default=(
                "[add_long_memory] an identical note is already saved "
                "(memory_id: %(memory_id)s)"
            ),
            memory_id=result["memory_id"],
        )
    if result["reason"] == "secret":
        return _(
            "err.secret",
            default=(
                "[add_long_memory error] note looks like it contains a "
                "credential; credentials must not be stored in memory"
            ),
        )
    if result["reason"] == "too_long":
        return _(
            "err.too_long",
            default="[add_long_memory error] note is too long; keep it to one concise note",
        )
    return _(
        "err.save",
        default="[add_long_memory error] failed to save memory",
    )


def describe(args: dict[str, Any]) -> str:
    """Localized pre-execution action line for UAGENT_SHOW_TOOL_RESULTS=2."""
    note = " ".join(str((args or {}).get("note") or "").split())
    if len(note) > 80:
        note = note[:79] + "…"
    if note:
        return _(
            "describe.add_with_note",
            default="Saving to long-term memory: %(note)s",
            note=note,
        )
    return _("describe.add", default="Saving to long-term memory")


TOOL_DESCRIBER = describe
