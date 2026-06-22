from __future__ import annotations

import json
import os
from typing import Any

from .email_utils import parse_email
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:gmail_read"

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "comm",
    "x_parallel_safe": False,
    "function": {
        "name": "gmail_read",
        "description": _(
            "tool.description",
            default="Read/search Gmail inbox via IMAP. Requires UAGENT_GMAIL_ADDRESS and UAGENT_GMAIL_APP_PASSWORD environment variables.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "gmail",
                "read email",
                "inbox",
                "mail search",
                "メール受信",
                "leer correo",
                "lire email",
                "이메일 읽기",
            ],
        ),
        "x_search_terms_en": [
            "gmail",
            "read email",
            "inbox",
            "mail search",
            "check email",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "search", "read", "unread"],
                    "description": _(
                        "param.action.description",
                        default="Action: list (recent inbox), search (by query), read (by message_id), unread (unread only).",
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": _(
                        "param.max_results.description",
                        default="Max results (default: 10, max: 50).",
                    ),
                    "default": 10,
                },
                "query": {
                    "type": "string",
                    "description": _(
                        "param.query.description",
                        default="Search query (used with action=search). IMAP format, e.g. 'FROM someone', 'SUBJECT hello', 'TEXT keyword'.",
                    ),
                },
                "message_id": {
                    "type": "string",
                    "description": _(
                        "param.message_id.description",
                        default="Message UID (used with action=read).",
                    ),
                },
            },
            "required": ["action"],
        },
    },
}


def _get_credentials() -> tuple[str | None, str | None]:
    addr = os.environ.get("UAGENT_GMAIL_ADDRESS")
    pwd = os.environ.get("UAGENT_GMAIL_APP_PASSWORD")
    return addr, pwd


def _parse_msg(uid: str, raw_data: bytes) -> dict[str, Any]:
    parsed = parse_email(raw_data)
    headers = parsed["headers"]
    body = parsed["body"]
    body_preview = body[:500] + "..." if len(body) > 500 else body
    return {
        "message_id": uid,
        "from": headers["from"],
        "to": headers["to"],
        "cc": headers["cc"],
        "subject": headers["subject"],
        "date": headers["date"],
        "body_preview": body_preview,
        "body": body,
    }


def run_tool(args: dict[str, Any]) -> str:
    try:
        addr, pwd = _get_credentials()
        if not addr or not pwd:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.credentials_missing",
                        default="UAGENT_GMAIL_ADDRESS and UAGENT_GMAIL_APP_PASSWORD must be set.",
                    ),
                },
                ensure_ascii=False,
            )

        action = str(args.get("action", "list")).strip()
        max_results = min(int(args.get("max_results", 10)), 50)
        query = str(args.get("query", "")).strip()
        message_id = str(args.get("message_id", "")).strip()

        # Validate action-specific params before connecting
        if action == "read" and not message_id:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.message_id_missing",
                        default="'message_id' is required for action=read.",
                    ),
                },
                ensure_ascii=False,
            )
        if action == "search" and not query:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.query_missing",
                        default="'query' is required for action=search.",
                    ),
                },
                ensure_ascii=False,
            )

        import imaplib

        server = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        try:
            server.login(addr, pwd)
        except imaplib.IMAP4.error:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.auth_failed",
                        default="IMAP authentication failed. Check UAGENT_GMAIL_ADDRESS and UAGENT_GMAIL_APP_PASSWORD.",
                    ),
                },
                ensure_ascii=False,
            )

        try:
            server.select("INBOX")

            if action == "unread":
                search_cmd = "UNSEEN"
            elif action == "search":
                search_cmd = query
            elif action == "read":
                status, data = server.uid("FETCH", message_id, "(RFC822)")
                if status != "OK" or not data or data[0] is None:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": _(
                                "err.message_not_found",
                                default="Message {uid} not found.",
                            ).format(uid=message_id),
                        },
                        ensure_ascii=False,
                    )
                raw_email = data[0][1]
                parsed = _parse_msg(message_id, raw_email)
                return json.dumps(
                    {
                        "ok": True,
                        "action": "read",
                        "message": parsed,
                    },
                    ensure_ascii=False,
                )
            else:  # list (default)
                search_cmd = "ALL"

            status, data = server.search(None, search_cmd)
            if status != "OK":
                return json.dumps(
                    {
                        "ok": False,
                        "error": _(
                            "err.search_failed",
                            default="IMAP search failed.",
                        ),
                    },
                    ensure_ascii=False,
                )

            uids = data[0].split() if data[0] else []
            if not uids:
                action_label = action if action != "list" else "inbox"
                return json.dumps(
                    {
                        "ok": True,
                        "action": action,
                        "messages": [],
                        "total": 0,
                        "message": _(
                            "msg.no_results",
                            default="No emails found ({action}).",
                        ).format(action=action_label),
                    },
                    ensure_ascii=False,
                )

            # Get latest N (IMAP returns oldest first, so take from end)
            uids = uids[-max_results:]
            messages: list[dict[str, Any]] = []
            for uid in uids:
                uid_str = uid.decode("ascii")
                fstatus, fdata = server.uid("FETCH", uid_str, "(RFC822)")
                if fstatus == "OK" and fdata[0] is not None:
                    raw_email = fdata[0][1]
                    parsed = _parse_msg(uid_str, raw_email)
                    # Remove full body from list results, keep preview
                    del parsed["body"]
                    messages.append(parsed)

            server.close()
            server.logout()

            action_label = action if action != "list" else "inbox"
            return json.dumps(
                {
                    "ok": True,
                    "action": action,
                    "messages": messages,
                    "total": len(messages),
                    "message": _(
                        "msg.results",
                        default="{count} email(s) found ({action}).",
                    ).format(count=len(messages), action=action_label),
                },
                ensure_ascii=False,
            )

        except Exception as e:
            try:
                server.close()
                server.logout()
            except Exception:
                pass
            return json.dumps(
                {"ok": False, "error": str(e)}, ensure_ascii=False
            )

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
