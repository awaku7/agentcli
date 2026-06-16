from __future__ import annotations

# src/uagent/tools/a2a_send_tool.py

import json
from typing import Any

from ..a2a.client import A2AClient
from .arg_util import get_bool, get_str
from .context import get_callbacks
from .i18n_helper import make_tool_translator
from .a2a_servers_tool import resolve_profile

_ = make_tool_translator(__file__)


def _json_ok(**obj: Any) -> str:
    out: dict[str, Any] = {"ok": True}
    out.update(obj)
    return json.dumps(out, ensure_ascii=False)


def _json_err(message: str, **extra: Any) -> str:
    out: dict[str, Any] = {"ok": False, "error": message}
    out.update(extra)
    return json.dumps(out, ensure_ascii=False)


TOOL_SPEC: dict[str, Any] = {
    "load_order": 9000,
    "type": "function",
    "tool_genre": "external",
    "function": {
        "name": "a2a_send",
        "description": _(
            "tool.description",
            default="Send a message to an A2A server profile. Use only when no local tool can substitute.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "a2a_send",
                "a2a send",
                "send message",
                "send request",
                "server profile",
                "profile message",
                "remote message",
                "messaging",
                "a2a message",
                "send task",
            ],
        ),
        "x_search_terms_en": [
            "a2a_send",
            "a2a send",
            "send message",
            "send request",
            "server profile",
            "profile message",
            "remote message",
            "messaging",
            "a2a message",
            "send task",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "description": _(
                        "param.profile.description",
                        default="Profile name or a2a://name. If omitted, uses default profile.",
                    ),
                },
                "message": {
                    "type": "string",
                    "description": _(
                        "param.message.description",
                        default="User message to send.",
                    ),
                },
                "return_immediately": {
                    "type": "boolean",
                    "description": _(
                        "param.return_immediately.description",
                        default="If true, return right after task creation.",
                    ),
                    "default": False,
                },
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, "tool:a2a_send")
    try:
        profile = get_str(args, "profile", "")
        message = get_str(args, "message", "")
        if not message:
            return _json_err(_("err.missing_message", default="Missing 'message'."))

        ret_immediately = get_bool(args, "return_immediately", False)

        prof = resolve_profile(profile or None)
        client = A2AClient(
            base_url=str(prof.get("base_url")),
            token=str(prof.get("token") or ""),
            timeout_sec=float(prof.get("timeout_s") or 300),
        )
        task = client.send_message(
            text=message, return_immediately=bool(ret_immediately)
        )
        # a2a_send returns the created task. Use a2a_poll to wait for completion.
        return _json_ok(task=task)

    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception"),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, "tool:a2a_send")
