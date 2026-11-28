# tools/search_past_sessions_tool.py

from __future__ import annotations

import json
from typing import Any

from ..runtime import text_terms
from ..runtime.identity_context import current_turn_is_local
from . import long_memory
from .context import get_callbacks
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = False

_DEFAULT_LIMIT = 5
_MAX_LIMIT = 10
_MAX_EXCERPTS_PER_SESSION = 3
_EXCERPT_CHARS = 200
_EXCERPT_LEAD_CHARS = 40
# Message-level fetch window before collapsing hits into sessions. The
# store returns hits oldest first, so a saturated window drops the
# newest hits; the result reports that as ``truncated`` instead of
# silently returning only old matches.
_SEARCH_WINDOW = 1000
_VISIBLE_ROLES = frozenset({"user", "assistant"})
_MIN_SCREEN_KEY_CHARS = 4


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_level": 1,
    "function": {
        "name": "search_past_sessions",
        "description": _(
            "tool.description",
            default=(
                "Search past conversations for topics the user says they discussed; return matching excerpts. Use session_resume to reopen one."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "search_past_sessions",
                "search past sessions",
                "past conversations",
                "discussed before",
                "previous conversation",
                "talked about earlier",
                "session search",
                "earlier discussion",
            ],
        ),
        "x_search_terms_en": [
            "search_past_sessions",
            "search past sessions",
            "past conversations",
            "discussed before",
            "previous conversation",
            "talked about earlier",
            "session search",
            "earlier discussion",
        ],
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {
                    "type": "string",
                    "description": _(
                        "param.query.description",
                        default=(
                            "Words or a phrase from the past conversation to look for "
                            "(a name, a topic, or wording the user used). For Japanese, "
                            "Chinese, Thai and Korean the search also matches extracted "
                            "words, so inflected forms are found; distinctive words "
                            "work best."
                        ),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": _MAX_LIMIT,
                    "description": _(
                        "param.limit.description",
                        default=(
                            "Maximum number of past sessions to return "
                            "(default 5, at most 10)."
                        ),
                    ),
                },
            },
            "required": ["query"],
        },
    },
}


def _result(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _clip(
    value: Any,
    query: str = "",
    terms: list[str] | None = None,
    limit: int = _EXCERPT_CHARS,
) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    # The store matches the query anywhere in a message, so clipping
    # from the start can hide the very text that matched. Center the
    # window on the first occurrence instead when it can be found.
    # Term matches (e.g. a Japanese verb's base form) may not appear
    # literally in the text, so extracted terms are tried after the
    # query itself and the window falls back to the start.
    needles = [query, *(terms or [])]
    match_at = -1
    folded = text.casefold()
    for needle in needles:
        if needle:
            match_at = folded.find(needle.casefold())
            if match_at >= 0:
                break
    start = max(0, match_at - _EXCERPT_LEAD_CHARS) if match_at >= 0 else 0
    clipped = text[start : start + limit]
    if start > 0:
        clipped = "…" + clipped[1:]
    if start + limit < len(text):
        clipped = clipped[:-1] + "…"
    return clipped


def _contains_forgotten(content: str, forgotten_keys: set[str]) -> bool:
    """Whether a past message restates a deliberately forgotten note.

    The comparison reuses the note normalization, so a message that
    carries the forgotten note's text (the realistic resurrection path,
    because notes are distilled from such messages) is withheld. A
    paraphrase of the forgotten fact cannot be caught by string
    matching; that is the same limit as the forget boundary itself.
    """
    # A floor on key length: a forgotten note that normalizes to a
    # very short key (a punctuation-only note normalizes to "") would
    # otherwise withhold unrelated messages wholesale. The forget
    # boundary's other paths compare whole notes exactly, so short
    # notes stay covered there.
    keys = [key for key in forgotten_keys if len(key) >= _MIN_SCREEN_KEY_CHARS]
    if not keys:
        return False
    key = long_memory.note_key_for(content)
    if not key:
        return False
    return any(forgotten in key for forgotten in keys)


def run_tool(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return _result(ok=False, error="query_empty")

    raw_limit = args.get("limit")
    if raw_limit is None or raw_limit == "":
        limit = _DEFAULT_LIMIT
    elif isinstance(raw_limit, bool):
        return _result(ok=False, error="invalid_limit")
    else:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return _result(ok=False, error="invalid_limit")
        if limit < 1:
            return _result(ok=False, error="invalid_limit")
        limit = min(limit, _MAX_LIMIT)

    callbacks = get_callbacks()
    store = callbacks.session_store
    if store is None:
        return _result(ok=False, error="session_store_unavailable")
    # Past sessions of every principal share one store on Web hosts, so
    # this fallback is fenced to the local identity, like the legacy
    # memory store it complements.
    if not current_turn_is_local():
        return _result(ok=False, error="local_sessions_only")

    try:
        hits = store.search(query, project=None, limit=_SEARCH_WINDOW)
    except TypeError:
        # Older/test adapters may not expose the optional limit.
        try:
            hits = store.search(query, project=None)
        except Exception:
            return _result(ok=False, error="search_failed")
    except Exception:
        return _result(ok=False, error="search_failed")

    try:
        forgotten_keys = long_memory.forgotten_note_keys_strict()
    except Exception:
        # Never fail open on the forget boundary: if the forgotten set
        # cannot be read, past content must not be resurfaced at all.
        return _result(ok=False, error="forget_screening_unavailable")

    truncated = len(hits or []) >= _SEARCH_WINDOW
    try:
        query_term_list = text_terms.query_terms(query)
    except Exception:
        query_term_list = []
    active_session_id = str(callbacks.session_id or "")
    sessions: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        session_id = str(hit.get("session_id") or "")
        if not session_id or session_id == active_session_id:
            continue
        if str(hit.get("entry_point") or "") == "sub-agent":
            continue
        role = str(hit.get("role") or "")
        if role not in _VISIBLE_ROLES:
            continue
        content = str(hit.get("content") or "")
        if not content.strip():
            continue
        if _contains_forgotten(content, forgotten_keys):
            continue
        entry = sessions.get(session_id)
        if entry is None:
            entry = {
                "session_id": session_id,
                "project": str(hit.get("project") or ""),
                "matches": 0,
                "latest_at": "",
                "excerpts": [],
            }
            sessions[session_id] = entry
            order.append(session_id)
        entry["matches"] += 1
        created_at = str(hit.get("created_at") or "")
        if created_at > entry["latest_at"]:
            entry["latest_at"] = created_at
        excerpts = entry["excerpts"]
        excerpts.append({"role": role, "text": _clip(content, query, query_term_list)})
        if len(excerpts) > _MAX_EXCERPTS_PER_SESSION:
            del excerpts[0]

    ranked = sorted(
        (sessions[session_id] for session_id in order),
        key=lambda entry: entry["latest_at"],
        reverse=True,
    )[:limit]
    return _result(
        ok=True,
        query=query,
        truncated=truncated,
        sessions=[
            {
                "session_id": entry["session_id"],
                "project": entry["project"],
                "matches": entry["matches"],
                "latest_match_at": entry["latest_at"],
                "excerpts": entry["excerpts"],
            }
            for entry in ranked
        ],
    )


def describe(args: dict[str, Any]) -> str:
    """Describe the search without echoing the query text."""
    return str(_("describe.search", default="Searching past sessions"))


TOOL_DESCRIBER = describe
