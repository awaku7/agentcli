# tools/change_workdir_tool.py
from __future__ import annotations

import os
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "tool_genre": "basic",
    "function": {
        "name": "change_workdir",
        "description": _(
            "tool.description",
            default="Change the current working directory after user confirmation.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "change directory",
                "cd",
                "switch dir",
                "ディレクトリ変更",
                "cambiar directorio",
                "changer de répertoire",
                "디렉터리 변경",
                "сменить директорию",
            ],
        ),
        "x_search_terms_en": [
            "change directory",
            "cd",
            "switch dir",
            "ディレクトリ変更",
            "cambiar directorio",
            "changer de répertoire",
            "디렉터리 변경",
            "сменить директорию",
        ],
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


def run_tool(args: dict[str, Any]) -> str:
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
        ).format(path=expanded, new_dir=expanded)
        res_json = human_ask({"message": msg})
        import json

        payload = json.loads(res_json)
        user_reply = (payload.get("user_reply", "") or "").strip().lower()
        cancelled = bool(payload.get("cancelled", False))
        if cancelled or user_reply not in ("y", "yes"):
            return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)

    prev = os.getcwd()
    os.chdir(expanded)
    now = os.getcwd()

    # Record workdir change to the log for later :load restoration
    try:
        from .context import get_callbacks
        import json

        cb = get_callbacks()
        if cb and cb.log_message:
            cwd_content = "[CWD] " + json.dumps(
                {
                    "event": "cd",
                    "path": now,
                    "prev": prev,
                    "src": new_dir,
                    "resolved": expanded,
                },
                ensure_ascii=False,
            )
            cb.log_message({"role": "system", "content": cwd_content})
    except Exception:
        pass

    return now
