from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from tools_rust import run_uuid_gen as run_tool  # noqa: E402

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_build": "rust",
    "tool_genre": "utility",
    "tool_level": 0,
    "function": {
        "name": "uuid_gen",
        "description": _(
            "tool.description",
            default="Generate one or more UUID v4 strings. Returns one per line.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["uuid", "uuid_gen", "generate uuid", "guid"],
        ),
        "x_search_terms_en": [
            "uuid",
            "uuid_gen",
            "generate uuid",
            "guid",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": _(
                        "tool.count",
                        default="Number of UUIDs to generate (1-100, default 1)",
                    ),
                }
            },
        },
    },
}
