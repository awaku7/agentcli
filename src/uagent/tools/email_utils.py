from __future__ import annotations

from email.header import decode_header
from typing import Any


def decode_email_header_value(val: bytes | str | None) -> str:
    """Decode an email header (RFC 2047) to plain text."""
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


def decode_email_payload(part: Any) -> str:
    """Decode a MIME part payload to text."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def get_email_body(msg: Any) -> str:
    """Extract the plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return decode_email_payload(part)
        # fallback: first text/* part
        for part in msg.walk():
            if part.get_content_maintype() == "text":
                return decode_email_payload(part)
        return ""
    return decode_email_payload(msg)


def get_email_attachments(msg: Any) -> list[dict[str, Any]]:
    """Extract attachment metadata from an email message."""
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
        decoded_filename = decode_email_header_value(filename)
        payload = part.get_payload(decode=True)
        attachments.append(
            {
                "filename": decoded_filename,
                "content_type": part.get_content_type(),
                "size": len(payload) if payload else 0,
            }
        )
    return attachments


def parse_email(raw_data: bytes) -> dict[str, Any]:
    """Parse raw email bytes into a structured dict."""
    import email

    msg = email.message_from_bytes(raw_data)
    return {
        "headers": {
            "from": decode_email_header_value(msg.get("From", "")),
            "to": decode_email_header_value(msg.get("To", "")),
            "cc": decode_email_header_value(msg.get("Cc", "")),
            "subject": decode_email_header_value(msg.get("Subject", "")),
            "date": msg.get("Date", ""),
            "message_id": msg.get("Message-ID", ""),
            "reply_to": msg.get("Reply-To", ""),
        },
        "body": get_email_body(msg),
        "attachments": get_email_attachments(msg),
    }
