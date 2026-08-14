from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from .i18n_helper import make_tool_translator
from .path_alias_shared import (
    load_url_aliases,
    save_url_aliases,
    url_alias_label,
)

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "x_parallel_safe": False,
    "function": {
        "name": "url_alias",
        "description": _(
            "tool.description",
            default="Register, list, or delete URL aliases @B{0} through @B{9}.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "list", "delete"],
                    "description": _(
                        "param.action.description", default="Operation to perform."
                    ),
                },
                "slot": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 9,
                    "description": _(
                        "param.slot.description",
                        default="Alias number; 0 produces @B{0}, 9 produces @B{9}.",
                    ),
                },
                "url": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Base URL to assign to the alias.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="Allow replacing an existing alias.",
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    "is_agent_content": False,
}

BUSY_LABEL = False


def _result(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _slot(args: dict[str, Any]) -> int | None:
    try:
        value = int(args.get("slot"))
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 9 else None


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip().lower()
    aliases = load_url_aliases()

    if action == "list":
        return _result(
            ok=True, aliases={url_alias_label(k): v for k, v in sorted(aliases.items())}
        )

    slot = _slot(args)
    if slot is None:
        return _result(ok=False, error="slot must be an integer from 0 to 9")

    if action == "delete":
        if slot not in aliases:
            return _result(
                ok=False, error=f"alias not registered: {url_alias_label(slot)}"
            )
        del aliases[slot]
        save_url_aliases(aliases)
        return _result(ok=True, deleted=url_alias_label(slot))

    if action == "set":
        url = str(args.get("url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return _result(ok=False, error="url must be an absolute http(s) URL")
        if slot in aliases and not bool(args.get("overwrite", False)):
            return _result(
                ok=False, error=f"alias already registered: {url_alias_label(slot)}"
            )
        aliases[slot] = url
        save_url_aliases(aliases)
        return _result(ok=True, alias=url_alias_label(slot))

    return _result(ok=False, error="action must be set, list, or delete")
