# tools/create_file_tool.py
from __future__ import annotations

import os
from typing import Any, Dict

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "create_file",
        "description": _(
            "tool.description",
            default=(
                "Create a text file (by default, do not overwrite if it already exists). "
                "If overwrite=true overwrites an existing file, a backup with the same name "
                "(<filename>.org / <filename>.org1 / ...) is created immediately before overwriting."
            ),
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'create_file'.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="Path of the file to create.",
                    ),
                },
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="(Compatibility) Alias of filename.",
                    ),
                },
                "content": {
                    "type": "string",
                    "description": _(
                        "param.content.description",
                        default="Text content to write to the file.",
                    ),
                },
                "encoding": {
                    "type": "string",
                    "description": _(
                        "param.encoding.description",
                        default="Text encoding (e.g., 'utf-8', 'cp932'). Defaults to 'utf-8'.",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="Whether to overwrite if the file already exists. Default is false.",
                    ),
                },
            },
            "required": ["content"],
        },
    },
}


def _backup_path(path: str) -> str:
    base = path + ".org"
    if not os.path.exists(base):
        return base
    i = 1
    while True:
        cand = f"{path}.org{i}"
        if not os.path.exists(cand):
            return cand
        i += 1


def run_tool(args: Dict[str, Any]) -> str:
    raw_filename = str(args.get("filename") or args.get("path") or "").strip()
    content = str(args.get("content", ""))
    encoding = str(args.get("encoding", "utf-8") or "utf-8")
    overwrite_raw = args.get("overwrite", None)
    overwrite = bool(overwrite_raw) if overwrite_raw is not None else False

    if not raw_filename:
        raise ValueError("filename/path is required")

    safe_path = ensure_within_workdir(raw_filename)

    if os.path.exists(safe_path) and not overwrite:
        raise FileExistsError(f"File already exists: {safe_path}")

    if os.path.exists(safe_path) and overwrite:
        # Create backup
        backup = _backup_path(safe_path)
        with open(safe_path, "rb") as fsrc, open(backup, "wb") as fdst:
            fdst.write(fsrc.read())

    os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
    with open(safe_path, "w", encoding=encoding, newline="") as f:
        f.write(content)

    return safe_path
