from __future__ import annotations

import os
from typing import Any

from uagent.tools.i18n_helper import make_tool_translator
from uagent.tools.rust_helper import load_rust_pyd

_ = make_tool_translator(__file__)

_rust_mod = load_rust_pyd(
    "uag_tools_rust",
    pyd_path=os.path.join(os.path.dirname(__file__), "target", "release", "uag_tools_rust.pyd"),
)
run_tool = _rust_mod.run_uuid_gen

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
