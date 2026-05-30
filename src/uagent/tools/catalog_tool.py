from __future__ import annotations

import json
from typing import Any

from ..env_utils import env_get
from . import get_tool_catalog
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_ENABLE_GPT54_TOOL_SEARCH = str(env_get("UAGENT_ENABLE_GPT54_TOOL_SEARCH") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if not _ENABLE_GPT54_TOOL_SEARCH:
    TOOL_SPEC = None  # type: ignore[assignment]
else:
    TOOL_SPEC: dict[str, Any] = {
        "type": "function",
        "function": {
            "name": "tool_catalog",
            "description": _(
                "tool.description",
                default=(
                    "Return a JSON catalog of available tools with ok, query, count, and tools fields so the model can discover relevant tools before requesting full tool definitions."
                ),
            ),
            "x_search_terms": _(
                "x_search_terms",
                default=[
                    "catalog",
                    "tool catalog",
                    "discover tools",
                    "tool discovery",
                ],
            ),
            "x_search_terms_en": [
                "catalog",
                "tool catalog",
                "discover tools",
                "tool discovery",
            ],
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": _(
                            "param.query.description",
                            default="Natural-language query describing the needed capability.",
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": _(
                            "param.max_results.description",
                            default="Maximum number of catalog entries to return.",
                        ),
                        "default": 12,
                    },
                },
                "required": ["query"],
            },
        },
    }


def run_tool(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    max_results_raw = args.get("max_results", 12)
    try:
        max_results = int(max_results_raw)
    except Exception:
        max_results = 12
    if max_results <= 0:
        max_results = 12

    catalog = get_tool_catalog(query=query, max_results=max_results)
    return json.dumps(
        {
            "ok": True,
            "query": query,
            "count": len(catalog),
            "tools": catalog,
        },
        ensure_ascii=False,
    )
