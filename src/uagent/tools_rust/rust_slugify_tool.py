from __future__ import annotations

from typing import Any

from uagent.tools.i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

from tools_rust import run_slugify as run_tool  # noqa: E402

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
