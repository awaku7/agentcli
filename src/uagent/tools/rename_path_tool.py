# -*- coding: utf-8 -*-
"""tools/rename_path_tool.py

Implementation of the rename_path tool.
"""

from __future__ import annotations
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


from typing import Any, Dict

from .safe_file_ops import safe_rename_path

BUSY_LABEL = True
STATUS_LABEL = "tool:rename_path"

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "rename_path",
        "description": _("tool.description", default="Rename (move) a file or directory."),
        "system_prompt": _(
            "tool.system_prompt",
            default=(
                "This tool renames or moves a file or directory.\n\n"
                "Safety Notes:\n"
                "- Confirmation is required for absolute paths, paths containing '..', or operations outside the workdir.\n"
                "- overwrite=true requires confirmation as it involves deletion of the destination."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "src": {
                    "type": "string",
                    "description": _(
                        "param.src.description",
                        default="The source path (file or directory). Relative path is recommended.",
                    ),
                },
                "dst": {
                    "type": "string",
                    "description": _(
                        "param.dst.description",
                        default="The destination path (file or directory). Relative path is recommended.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="If true, delete and replace the destination if it already exists (requires confirmation).",
                    ),
                    "default": False,
                },
                "mkdirs": {
                    "type": "boolean",
                    "description": _(
                        "param.mkdirs.description",
                        default="If true, create the parent directory of the destination before execution.",
                    ),
                    "default": False,
                },
            },
            "required": ["src", "dst"],
        },
    },
}


def run_tool(args: Dict[str, Any]) -> str:
    src = str(args.get("src") or "").strip()
    dst = str(args.get("dst") or "").strip()

    overwrite = bool(args.get("overwrite", False))
    mkdirs = bool(args.get("mkdirs", False))

    try:
        safe_rename_path(src=src, dst=dst, overwrite=overwrite, mkdirs=mkdirs)
    except Exception as e:
        return f"[rename_path error] {type(e).__name__}: {e}"

    return f"[OK] renamed: {src} -> {dst}"
