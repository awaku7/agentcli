from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator
from .path_alias_shared import alias_label, load_aliases, save_aliases

_ = make_tool_translator(__file__)

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "x_parallel_safe": False,
    "function": {
        "name": "path_alias",
        "description": _(
            "tool.description",
            default="Register, list, or delete short path aliases @A{0} through @A{9}.",
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
                        default="Alias number; 0 produces @A{0}, 9 produces @A{9}.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Directory to assign to the alias.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="For set, allow replacing an existing alias.",
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


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip().lower()
    aliases = load_aliases()

    if action == "list":
        visible = dict(aliases)
        if 0 not in visible:
            visible[0] = Path.cwd()
        return _result(
            ok=True,
            aliases={
                alias_label(slot): str(path) for slot, path in sorted(visible.items())
            },
        )

    if action == "delete":
        try:
            slot = int(args.get("slot"))
        except (TypeError, ValueError):
            return _result(
                ok=False,
                error=_("err.slot", default="slot must be an integer from 0 to 9"),
            )
        if not 0 <= slot <= 9:
            return _result(
                ok=False,
                error=_("err.slot", default="slot must be an integer from 0 to 9"),
            )
        if slot not in aliases:
            return _result(ok=False, error=f"alias not registered: {alias_label(slot)}")
        del aliases[slot]
        save_aliases(aliases)
        return _result(ok=True, deleted=alias_label(slot))

    if action == "set":
        try:
            slot = int(args.get("slot"))
        except (TypeError, ValueError):
            return _result(
                ok=False,
                error=_("err.slot", default="slot must be an integer from 0 to 9"),
            )
        if not 0 <= slot <= 9:
            return _result(
                ok=False,
                error=_("err.slot", default="slot must be an integer from 0 to 9"),
            )
        raw_path = str(args.get("path") or "").strip()
        if not raw_path:
            return _result(ok=False, error="path is required")
        if slot in aliases and not bool(args.get("overwrite", False)):
            return _result(
                ok=False, error=f"alias already registered: {alias_label(slot)}"
            )
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            return _result(ok=False, error="path must be an existing directory")
        aliases[slot] = path
        save_aliases(aliases)
        return _result(ok=True, alias=alias_label(slot))

    return _result(ok=False, error="action must be set, list, or delete")
