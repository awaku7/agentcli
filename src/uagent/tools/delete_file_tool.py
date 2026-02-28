# tools/delete_file_tool.py
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": _(
            "tool.description",
            default=(
                "Delete the specified file or directory (directories are deleted recursively). "
                "Because this is dangerous, confirmation may be required."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'delete_file'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="Path to the file to delete.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="(Compatibility) Alias of filename.",
                    ),
                },
                "missing_ok": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.missing_ok.description",
                        default="If true, do not error when the path does not exist.",
                    ),
                },
            },
            "required": [],
        },
    },
}


def _human_confirm(message: str) -> bool:
    try:
        from .human_ask_tool import run_tool as human_ask

        res_json = human_ask({"message": message})
        payload = json.loads(res_json)
        user_reply = (payload.get("user_reply") or "").strip().lower()
        cancelled = bool(payload.get("cancelled", False))
        return (not cancelled) and user_reply in ("y", "yes")
    except Exception:
        return False


def run_tool(args: Dict[str, Any]) -> str:
    raw_filename = str(args.get("filename") or args.get("path") or "").strip()
    missing_ok = bool(args.get("missing_ok", False))

    if not raw_filename:
        raise ValueError("filename/path is required")

    safe_path = ensure_within_workdir(raw_filename)

    if not os.path.exists(safe_path):
        if missing_ok:
            return json.dumps({"ok": True, "deleted": False, "path": safe_path})
        raise FileNotFoundError(safe_path)

    # Confirm dangerous operation.
    msg = _(
        "confirm.delete_path",
        default="Delete path: {path}?\nEnter y to proceed, or c to cancel.",
    ).format(path=safe_path)
    if not _human_confirm(msg):
        return json.dumps({"ok": False, "cancelled": True}, ensure_ascii=False)

    if os.path.isdir(safe_path):
        shutil.rmtree(safe_path)
    else:
        os.remove(safe_path)

    return json.dumps(
        {"ok": True, "deleted": True, "path": safe_path}, ensure_ascii=False
    )
