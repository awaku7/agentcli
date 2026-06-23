from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .email_utils import (
    parse_email,
)
from .i18n_helper import make_tool_translator
from .safe_file_ops_extras import ensure_within_workdir

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:parse_eml"

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "file",
    "x_parallel_safe": True,
    "function": {
        "name": "parse_eml",
        "description": _(
            "tool.description",
            default="Parse a .eml email file and extract headers (From/To/Subject/Date) and body text.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "eml",
                "email",
                "mail",
                "outlook",
                "メールファイル",
                "parse email",
                "eml parser",
                "archivo eml",
                "fichier eml",
            ],
        ),
        "x_search_terms_en": [
            "eml",
            "email",
            "mail",
            "outlook",
            "parse email",
            "eml parser",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": _(
                        "param.path.description",
                        default="Path to the .eml file.",
                    ),
                },
                "max_body_length": {
                    "type": "integer",
                    "description": _(
                        "param.max_body_length.description",
                        default="Max characters for body extraction (default: 5000, 0 = unlimited).",
                    ),
                    "default": 5000,
                },
            },
            "required": ["path"],
        },
    },
}





def run_tool(args: dict[str, Any]) -> str:
    try:
        raw_path = str(args.get("path", "")).strip()
        max_body = int(args.get("max_body_length", 5000))

        if not raw_path:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.path_missing", default="path is required."
                    ),
                },
                ensure_ascii=False,
            )

        safe_path = ensure_within_workdir(raw_path)
        if not os.path.isfile(safe_path):
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.file_not_found",
                        default="File not found: {path}",
                    ).format(path=safe_path),
                },
                ensure_ascii=False,
            )

        ext = Path(safe_path).suffix.lower()
        if ext != ".eml":
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.invalid_extension",
                        default="Expected .eml file, got: {ext}",
                    ).format(ext=ext),
                },
                ensure_ascii=False,
            )

        with open(safe_path, "rb") as f:
            raw_data = f.read()

        parsed = parse_email(raw_data)
        headers = parsed["headers"]
        body = parsed["body"]
        if max_body > 0 and len(body) > max_body:
            body = body[:max_body] + f"\n... [truncated at {max_body} chars]"

        attachments = parsed["attachments"]

        payload = {
            "ok": True,
            "path": safe_path,
            "headers": {
                "from": headers["from"],
                "to": headers["to"],
                "cc": headers["cc"],
                "subject": headers["subject"],
                "date": headers["date"],
                "message_id": headers["message_id"],
                "reply_to": headers["reply_to"],
            },
            "body": body,
            "attachments": attachments,
            "body_length": len(body),
            "attachment_count": len(attachments),
        }
        return json.dumps(payload, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
