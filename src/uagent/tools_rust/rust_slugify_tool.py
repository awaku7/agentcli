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
run_tool = _rust_mod.run_slugify

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_build": "rust",
    "tool_genre": "utility",
    "tool_level": 0,
    "function": {
        "name": "slugify",
        "description": _(
            "tool.description",
            default="Convert text to a URL-friendly slug (e.g. 'Hello World' -> 'hello-world').",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["slugify", "slug", "url slug", "text to slug"],
        ),
        "x_search_terms_en": [
            "slugify",
            "slug",
            "url slug",
            "text to slug",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": _("tool.text", default="Text to convert to a slug"),
                },
                "separator": {
                    "type": "string",
                    "description": _(
                        "tool.separator",
                        default="Word separator (default: '-')",
                    ),
                },
            },
            "required": ["text"],
        },
    },
}
