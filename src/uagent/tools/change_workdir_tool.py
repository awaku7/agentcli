# tools/change_workdir_tool.py
from __future__ import annotations

import os
from typing import Any, Dict

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "change_workdir",
        "description": _(
            "tool.description",
            default="Change the current working directory after user confirmation.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'change_workdir'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "new_dir": {
                    "type": "string",
                    "description": _(
                        "param.new_dir.description",
                        default="The new directory path to switch to. Required.",
                    ),
                },
                "confirm": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.confirm.description",
                        default="Whether to ask for user confirmation. Default is True.",
                    ),
                },
            },
            "required": ["new_dir"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    new_dir = str(args.get("new_dir") or "").strip()
    confirm = bool(args.get("confirm", True))

    if not new_dir:
        raise ValueError("new_dir is required")

    # Resolve ~ etc.
    expanded = os.path.expanduser(new_dir)
    expanded = os.path.abspath(expanded)

    if confirm:
        from .human_ask_tool import run_tool as human_ask

        msg = _(
            "confirm.change_workdir",
            default="Change workdir to: {path}?\nEnter y to proceed, or c to cancel.",
        ).format(path=expanded)
        res_json = human_ask({"message": msg})
        import json

        payload = json.loads(res_json)
        user_reply = (payload.get("user_reply", "") or "").strip().lower()
        cancelled = bool(payload.get("cancelled", False))
        if cancelled or user_reply not in ("y", "yes"):
            return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)

    os.chdir(expanded)
    return os.getcwd()
