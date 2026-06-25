# tools/create_file_tool.py

from __future__ import annotations

import json
import os
from typing import Any

from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "function": {
        "name": "create_file",
        "description": _(
            "tool.description",
            default="Create a text file. Optional overwrite with backup (.org). Choose encoding for Excel (utf-8-sig) or programmatic (utf-8).",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "create file",
                "new file",
                "write file",
                "ファイルを作成",
                "crear archivo",
                "créer fichier",
                "파일 만들기",
                "создать файл",
            ],
        ),
        "x_search_terms_en": [
            "create file",
            "new file",
            "write file",
            "ファイルを作成",
            "crear archivo",
            "créer fichier",
            "파일 만들기",
            "создать файл",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": _(
                        "param.filename.description",
                        default="File path to create.",
                    ),
                },
                "content": {
                    "type": "string",
                    "description": _(
                        "param.content.description",
                        default="Text content.",
                    ),
                },
                "encoding": {
                    "type": "string",
                    "description": _(
                        "param.encoding.description",
                        default="Encoding (e.g. utf-8, cp932; default: utf-8).",
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": _(
                        "param.overwrite.description",
                        default="Overwrite if exists (default: false).",
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


def run_tool(args: dict[str, Any]) -> str:
    try:
        raw_filename = str(args.get("filename") or args.get("path") or "").strip()
        content = str(args.get("content", ""))
        encoding_raw = args.get("encoding")
        if encoding_raw is None or str(encoding_raw).strip() == "":
            ext = os.path.splitext(raw_filename)[1].lower()
            encoding = "utf-8-sig" if ext in (".csv", ".tsv") else "utf-8"
        else:
            encoding = str(encoding_raw)
        overwrite_raw = args.get("overwrite", False)
        if not isinstance(overwrite_raw, bool):
            return json.dumps(
                {"ok": False, "error": "overwrite must be a boolean"},
                ensure_ascii=False,
            )
        overwrite = overwrite_raw

        if not raw_filename:
            return json.dumps(
                {
                    "ok": False,
                    "error": _("err.path_missing", default="filename/path is required"),
                },
                ensure_ascii=False,
            )

        safe_path = ensure_within_workdir(raw_filename)
        existed_before = os.path.exists(safe_path)

        if existed_before and not overwrite:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.file_exists",
                        default="File already exists: {path}",
                    ).format(path=safe_path),
                },
                ensure_ascii=False,
            )

        backup_path = None
        if existed_before and overwrite:
            backup_path = _backup_path(safe_path)
            with open(safe_path, "rb") as fsrc, open(backup_path, "wb") as fdst:
                fdst.write(fsrc.read())

        os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
        with open(safe_path, "w", encoding=encoding, newline="") as f:
            f.write(content)

        payload = {
            "ok": True,
            "path": safe_path,
            "created": not existed_before,
            "overwritten": bool(existed_before and overwrite),
            "backup_path": backup_path,
            "encoding": encoding,
            "message": (
                _("msg.created", default="Created file: {path}").format(path=safe_path)
                if not existed_before
                else _("msg.overwrote", default="Overwrote file: {path}").format(
                    path=safe_path
                )
            ),
        }
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
