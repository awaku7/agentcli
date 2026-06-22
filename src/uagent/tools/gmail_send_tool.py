from __future__ import annotations

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:gmail_send"

TOOL_SPEC: dict[str, Any] = {
    "load_order": -1,
    "type": "function",
    "tool_genre": "comm",
    "x_parallel_safe": False,
    "function": {
        "name": "gmail_send",
        "description": _(
            "tool.description",
            default="Send an email via Gmail SMTP using App Password. Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD environment variables.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "gmail",
                "send email",
                "mail",
                "メール送信",
                "enviar correo",
                "envoyer email",
                "이메일 보내기",
            ],
        ),
        "x_search_terms_en": [
            "gmail",
            "send email",
            "mail",
            "send mail",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": _(
                        "param.to.description",
                        default="Recipient email address(es). Comma-separated for multiple.",
                    ),
                },
                "subject": {
                    "type": "string",
                    "description": _(
                        "param.subject.description",
                        default="Email subject.",
                    ),
                },
                "body": {
                    "type": "string",
                    "description": _(
                        "param.body.description",
                        default="Email body text (plain text).",
                    ),
                },
                "cc": {
                    "type": "string",
                    "description": _(
                        "param.cc.description",
                        default="CC recipient email address(es). Comma-separated.",
                    ),
                },
                "bcc": {
                    "type": "string",
                    "description": _(
                        "param.bcc.description",
                        default="BCC recipient email address(es). Comma-separated.",
                    ),
                },
                "html": {
                    "type": "boolean",
                    "description": _(
                        "param.html.description",
                        default="If true, body is treated as HTML. Default: false.",
                    ),
                    "default": False,
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
}


def _get_credentials() -> tuple[str | None, str | None]:
    addr = os.environ.get("UAGENT_GMAIL_ADDRESS")
    pwd = os.environ.get("UAGENT_GMAIL_APP_PASSWORD")
    return addr, pwd


def run_tool(args: dict[str, Any]) -> str:
    try:
        to_raw = str(args.get("to", "")).strip()
        subject = str(args.get("subject", "")).strip()
        body = str(args.get("body", ""))
        cc_raw = str(args.get("cc", "")).strip()
        bcc_raw = str(args.get("bcc", "")).strip()
        is_html = bool(args.get("html", False))

        if not to_raw:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.to_missing", default="'to' field is required."
                    ),
                },
                ensure_ascii=False,
            )
        if not subject:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.subject_missing", default="'subject' field is required."
                    ),
                },
                ensure_ascii=False,
            )

        addr, pwd = _get_credentials()
        if not addr or not pwd:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.credentials_missing",
                        default="GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in environment variables.",
                    ),
                },
                ensure_ascii=False,
            )

        # Normalise recipient lists
        to_list = [e.strip() for e in to_raw.split(",") if e.strip()]
        cc_list = [e.strip() for e in cc_raw.split(",") if e.strip()] if cc_raw else []
        bcc_list = (
            [e.strip() for e in bcc_raw.split(",") if e.strip()] if bcc_raw else []
        )

        all_recipients = to_list + cc_list + bcc_list
        if not all_recipients:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.no_recipients",
                        default="No valid recipients specified.",
                    ),
                },
                ensure_ascii=False,
            )

        # Build message
        msg = MIMEMultipart("alternative")
        msg["From"] = addr
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)

        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        # Send via SMTP SSL
        try:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
            server.login(addr, pwd)
            server.sendmail(addr, all_recipients, msg.as_string())
            server.quit()
        except smtplib.SMTPAuthenticationError:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.auth_failed",
                        default="SMTP authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD.",
                    ),
                },
                ensure_ascii=False,
            )
        except smtplib.SMTPRecipientsRefused as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.recipients_refused",
                        default="Recipient(s) refused: {detail}",
                    ).format(detail=str(e)),
                },
                ensure_ascii=False,
            )
        except smtplib.SMTPServerDisconnected:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.server_disconnected",
                        default="SMTP server disconnected unexpectedly.",
                    ),
                },
                ensure_ascii=False,
            )
        except smtplib.SMTPException as e:
            return json.dumps(
                {
                    "ok": False,
                    "error": _(
                        "err.smtp_error",
                        default="SMTP error: {detail}",
                    ).format(detail=str(e)),
                },
                ensure_ascii=False,
            )

        payload = {
            "ok": True,
            "from": addr,
            "to": to_list,
            "cc": cc_list,
            "bcc": bcc_list,
            "subject": subject,
            "message": _(
                "msg.sent",
                default="Email sent to {count} recipient(s).",
            ).format(count=len(all_recipients)),
        }
        return json.dumps(payload, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
