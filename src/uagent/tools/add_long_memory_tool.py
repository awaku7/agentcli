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
    "tool_level": 1,
    "function": {
        "name": "add_long_memory",
        "description": _(
            "tool.description",
            default=(
                "Store durable user/environment facts as long-term memory. Do not save secrets or one-off details; update duplicates and set supersedes when facts change."
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
                "supersedes": {
                    "type": "string",
                    "description": _(
                        "param.supersedes.description",
                        default=(
                            "Optional memory_id of the existing note this one replaces when a fact has changed "
                            "(look it up with get_long_memory first). The replaced note stops being retrieved "
                            "but stays restorable, and background re-learning will not bring it back."
                        ),
                    ),
                },
                "aliases": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": _(
                        "param.aliases.description",
                        default=(
                            "Optional alternative phrasings of this note (synonyms, abbreviations, "
                            "or another language) that future conversations might use for the same "
                            "fact. Retrieval matches these too, so the note is still found when "
                            "different words are used. Keep each phrasing short; up to 8 are kept."
                        ),
                    ),
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
    supersedes = str(args.get("supersedes") or "").strip()
    result = long_memory.save_long_memory(
        note,
        owner=owner,
        project=project,
        source="tool",
        supersedes_id=supersedes,
        aliases=args.get("aliases"),
    )
    if result["saved"]:
        if result.get("superseded_id"):
            return _(
                "result.saved_superseded",
                default=(
                    "[add_long_memory] saved (memory_id: %(memory_id)s), "
                    "superseded (memory_id: %(superseded_id)s)"
                ),
                memory_id=result["memory_id"],
                superseded_id=result["superseded_id"],
            )
        return _(
            "result.saved",
            default="[add_long_memory] saved (memory_id: %(memory_id)s)",
            memory_id=result["memory_id"],
        )
    if result["reason"] == "duplicate":
        if result.get("superseded_id"):
            return _(
                "result.duplicate_superseded",
                default=(
                    "[add_long_memory] an identical note is already saved "
                    "(memory_id: %(memory_id)s), superseded "
                    "(memory_id: %(superseded_id)s)"
                ),
                memory_id=result["memory_id"],
                superseded_id=result["superseded_id"],
            )
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
    """Describe the memory operation without echoing the private note."""
    return str(_("describe.add", default="Saving to long-term memory"))


TOOL_DESCRIBER = describe
