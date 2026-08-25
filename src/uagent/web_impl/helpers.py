"""Web helper functions (split from web.py)."""

from __future__ import annotations

import json
import re
from typing import Any

from .. import util_tools as tools_util
from ..utils.paths import get_history_file_path

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Drop whole-line and mid-line [STATE] markers (status is sent via type=status).
_STATE_TOKEN_RE = re.compile(r"\[STATE\]\s+\w+(?:\s+\[[^\]]*\])?")


def _strip_state_markers(text: str) -> str:
    """Remove [STATE] ... tokens from log text; return empty if only status noise."""
    if not text or "[STATE]" not in text:
        return text
    cleaned = _STATE_TOKEN_RE.sub("", text)
    # If the line was only status (plus whitespace), drop it entirely.
    if not cleaned.strip():
        return ""
    return cleaned


def _load_input_history() -> list[str]:
    """Load input history from shared CLI history file."""
    try:
        p = get_history_file_path()
        if p.exists():
            result = []
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("+") and len(line) > 1:
                    result.append(line[1:])
            return result
    except Exception:
        pass
    return []


def _save_input_history(text: str) -> None:
    """Append to the shared CLI history file."""
    try:
        t = text.replace("\r", "").strip()
        if not t:
            return
        p = get_history_file_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        # Read existing entries to avoid duplicates
        existing = set()
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("+") and len(line) > 1:
                    existing.add(line[1:])
        if t not in existing:
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"+{t}\n")
    except Exception:
        pass


def _enrich_message_attachments(msg: dict[str, Any]) -> dict[str, Any]:
    display_msg = dict(msg or {})

    # Try to extract attachments from tool result JSON content
    attachments = display_msg.get("attachments")
    if not isinstance(attachments, list) or not attachments:
        content = display_msg.get("content", "")
        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    # make_response format: {"ok": ..., "data": {"attachments": [...]}}
                    data = parsed.get("data")
                    if isinstance(data, dict):
                        data_attachments = data.get("attachments")
                        if isinstance(data_attachments, list) and data_attachments:
                            attachments = data_attachments
                            display_msg["attachments"] = attachments
                    # Also check top-level attachments in parsed
                    top_att = parsed.get("attachments")
                    if isinstance(top_att, list) and top_att:
                        attachments = top_att
                        display_msg["attachments"] = attachments
            except (json.JSONDecodeError, TypeError):
                pass

    if isinstance(attachments, list) and attachments:
        enriched = []
        for att in attachments:
            if not isinstance(att, dict):
                enriched.append(att)
                continue
            item = dict(att)
            path = item.get("path") or item.get("saved_path") or item.get("file_path")
            mime = str(item.get("mime") or item.get("type") or "").lower()
            b64 = item.get("data_base64") or item.get("base64")
            if isinstance(b64, str) and b64 and not item.get("data_url"):
                item["data_url"] = (
                    f"data:{mime if mime.startswith('image/') else 'image/png'};base64,{b64}"
                )
            if (
                path
                and not item.get("data_url")
                and (mime.startswith("image/") or mime in ("image", ""))
            ):
                try:
                    item["data_url"] = tools_util.image_file_to_data_url(str(path))
                except Exception:
                    pass
            enriched.append(item)
        display_msg["attachments"] = enriched
        # Simplify content for tool messages with image attachments
        role = display_msg.get("role")
        if role == "tool":
            c = display_msg.get("content", "")
            if isinstance(c, str) and c.strip().startswith("{"):
                try:
                    parsed = json.loads(c)
                    if isinstance(parsed, dict):
                        msg_text = parsed.get("message", "")
                        if msg_text:
                            display_msg["content"] = msg_text
                except (json.JSONDecodeError, TypeError):
                    pass
    return display_msg


def _lang_from_accept_language(v: str | None) -> str:
    """Parse Accept-Language and return 'ja' or 'en'.

    Web policy (B): browser language is authoritative.
    """
    if not v:
        return "en"
    s = str(v)
    # Simple parse: split by comma, take primary tags, keep order
    parts: list[str] = []
    for item in s.split(","):
        item = item.strip()
        if not item:
            continue
        tag = item.split(";", 1)[0].strip().lower()
        if tag:
            parts.append(tag)
    for tag in parts:
        if tag.startswith("ja"):
            return "ja"
    return "en"
