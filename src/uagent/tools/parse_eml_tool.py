from __future__ import annotations

import email
import json
import os
from email.header import decode_header
from pathlib import Path
from typing import Any

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


def _decode_header_value(val: bytes | str | None) -> str:
    if val is None:
        return ""
    if isinstance(val, bytes):
        val = val.decode("utf-8", errors="replace")
    parts = decode_header(val)
    out: list[str] = []
    for data, charset in parts:
        if isinstance(data, bytes):
            try:
                out.append(data.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                out.append(data.decode("utf-8", errors="replace"))
        else:
            out.append(data)
    return " ".join(out)


def _decode_payload(part: Any) -> str:
    cte = part.get("Content-Transfer-Encoding", "").lower()
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def _get_body(msg: Any) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                return _decode_payload(part)
        for part in msg.walk():
            if part.get_content_maintype() == "text":
                return _decode_payload(part)
        return ""
    return _decode_payload(msg)


def _get_attachments(msg: Any) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        if "attachment" not in content_disposition.lower():
            continue
        filename = part.get_filename()
        if not filename:
            continue
        decoded_filename = _decode_header_value(filename)
        payload = part.get_payload(decode=True)
        attachments.append(
            {
                "filename": decoded_filename,
                "content_type": part.get_content_type(),
                "size": len(payload) if payload else 0,
            }
        )
    return attachments


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

        msg = email.message_from_bytes(raw_data)

        subject = _decode_header_value(msg.get("Subject", ""))
        sender = _decode_header_value(msg.get("From", ""))
        recipient = _decode_header_value(msg.get("To", ""))
        cc = _decode_header_value(msg.get("Cc", ""))
        date = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")
        reply_to = msg.get("Reply-To", "")

        body = _get_body(msg)
        if max_body > 0 and len(body) > max_body:
            body = body[:max_body] + f"\n... [truncated at {max_body} chars]"

        attachments = _get_attachments(msg)

        payload = {
            "ok": True,
            "path": safe_path,
            "headers": {
                "from": sender,
                "to": recipient,
                "cc": cc,
                "subject": subject,
                "date": date,
                "message_id": message_id,
                "reply_to": reply_to,
            },
            "body": body,
            "attachments": attachments,
            "body_length": len(body),
            "attachment_count": len(attachments),
        }
        return json.dumps(payload, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
