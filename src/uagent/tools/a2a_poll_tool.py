from __future__ import annotations

# src/uagent/tools/a2a_poll_tool.py

import json
from typing import Any

from ..a2a.client import A2AClient
from .arg_util import get_int, get_str
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
    "x_parallel_safe": True,
    "tool_genre": "external",
    "function": {
        "name": "a2a_poll",
        "description": _(
            "tool.description",
            default="Poll an A2A task until terminal state. Use only when no local tool can substitute.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "a2a_poll",
                "a2a poll",
                "poll task",
                "check status",
                "wait for task",
                "task status",
                "poll result",
                "task polling",
                "progress check",
                "monitor task",
            ],
        ),
        "x_search_terms_en": [
            "a2a_poll",
            "a2a poll",
            "poll task",
            "check status",
            "wait for task",
            "task status",
            "poll result",
            "task polling",
            "progress check",
            "monitor task",
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
                "task_id": {
                    "type": "string",
                    "description": _(
                        "param.task_id.description",
                        default="Task ID to poll.",
                    ),
                },
                "interval_ms": {
                    "type": "integer",
                    "description": _(
                        "param.interval_ms.description",
                        default="Override polling interval (ms).",
                    ),
                },
                "timeout_s": {
                    "type": "integer",
                    "description": _(
                        "param.timeout_s.description",
                        default="Override timeout (seconds).",
                    ),
                },
            },
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    cb = get_callbacks()
    if cb.set_status:
        cb.set_status(True, "tool:a2a_poll")
    try:
        profile = get_str(args, "profile", "")
        task_id = get_str(args, "task_id", "")
        if not task_id:
            return _json_err(_("err.missing_task_id", default="Missing 'task_id'."))

        prof = resolve_profile(profile or None)

        interval_ms = get_int(args, "interval_ms", int(prof.get("interval_ms") or 500))
        timeout_s = get_int(args, "timeout_s", int(prof.get("timeout_s") or 300))

        client = A2AClient(
            base_url=str(prof.get("base_url")),
            token=str(prof.get("token") or ""),
            timeout_sec=float(timeout_s),
        )

        final_task = client.poll_task(task_id=task_id, interval_ms=int(interval_ms))
        return _json_ok(task=final_task)

    except Exception as e:
        return _json_err(
            _("err.exception", default="Exception"),
            exception=type(e).__name__,
            detail=str(e),
        )
    finally:
        if cb.set_status:
            cb.set_status(False, "tool:a2a_poll")
