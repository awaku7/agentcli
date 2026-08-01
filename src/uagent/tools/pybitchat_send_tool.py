"""pybitchat_send_tool: send messages over the BLE Mesh."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from .i18n_helper import make_tool_translator
from .pybitchat_shared import ensure_dependencies, enqueue_send

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:pybitchat_send"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "comm",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "pybitchat_send",
        "description": _(
            "tool.description",
            default=(
                "Send a text message, announce, or leave over the pybitchat BLE Mesh. "
                "The node must be running (pybitchat_subscribe action=start)."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "pybitchat send",
                "bitchat send",
                "pybitchat_send",
                "message",
            ],
        ),
        "x_search_terms_en": [
            "pybitchat send",
            "bitchat send",
            "message",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["text", "announce", "leave", "file"],
                    "description": _(
                        "param.type.description",
                        default="Message type: text (chat message), announce (node announcement), leave (go offline), or file (send a file by path).",
                    ),
                },
                "payload": {
                    "type": "string",
                    "description": _(
                        "param.payload.description",
                        default="Message content (text) or nickname (announce).",
                    ),
                },
                "recipient": {
                    "type": ["string", "null"],
                    "default": None,
                    "description": _(
                        "param.recipient.description",
                        default="Optional recipient peer ID. None = broadcast.",
                    ),
                },
                "via": {
                    "type": "string",
                    "enum": ["ble", "nostr", "both"],
                    "default": "ble",
                    "description": _(
                        "param.via.description",
                        default="Transport: 'ble' (BLE Mesh), 'nostr' (Nostr relays), 'both'.",
                    ),
                },
                "plain": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.plain.description",
                        default=(
                            "Force plain-text (unencrypted) DM. Skips the Noise handshake. "
                            "Use when Noise handshake fails with the Android app."
                        ),
                    ),
                },
            },
            "required": ["type", "payload"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    msg_type = str(args.get("type") or "").strip()
    payload = str(args.get("payload") or "").strip()
    recipient = args.get("recipient") or None
    via = str(args.get("via") or "ble").strip()
    plain = bool(args.get("plain") or False)

    if not payload:
        return json.dumps(
            {"ok": False, "error": "payload is required"},
            ensure_ascii=False,
        )

    ensure_dependencies()
    if msg_type == "file":
        os_path = __import__("os").path
        if not os_path.exists(os_path.expanduser(payload)):
            return json.dumps(
                {"ok": False, "error": f"File not found: {payload}"},
                ensure_ascii=False,
            )
    enqueue_send(msg_type, payload, recipient=recipient, via=via, plain=plain)

    result = {
        "ok": True,
        "message_id": str(uuid4()),
        "type": msg_type,
        "payload_size": len(payload),
        "via": via,
    }
    if recipient:
        result["recipient"] = recipient
    if plain:
        result["plain"] = True

    return json.dumps(result, ensure_ascii=False)
