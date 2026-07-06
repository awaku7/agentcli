from __future__ import annotations

import json
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:opcua_unsubscribe"

_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {}


def set_subscriptions_ref(ref: dict[str, dict[str, Any]]) -> None:
    """Set reference to subscriptions dict from subscribe tool."""
    global _SUBSCRIPTIONS
    _SUBSCRIPTIONS = ref


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "opcua_unsubscribe",
        "description": _(
            "tool.description",
            default=(
                "Cancel an OPC UA subscription by subscription_id, "
                "or list active subscriptions."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["unsubscribe", "list"],
                    "default": "unsubscribe",
                    "description": _(
                        "param.action.description",
                        default="Action: 'unsubscribe' (default) or 'list'.",
                    ),
                },
                "subscription_id": {
                    "type": "string",
                    "description": _(
                        "param.subscription_id.description",
                        default="Subscription ID to cancel (required for action=unsubscribe).",
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description",
                        default="Format: json or text.",
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
}


def _format_list(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    subs = payload.get("subscriptions") or []
    if not subs:
        return _("msg.no_subscriptions", default="No active OPC UA subscriptions.")
    lines = [
        _(
            "msg.header",
            default="Active OPC UA subscriptions ({count}):",
            count=len(subs),
        )
    ]
    for s in subs:
        lines.append(
            f"  [{s.get('subscription_id')}] {s.get('label', '?')} @ {s.get('url')}"
        )
    return "\n".join(lines).strip()


def _format_unsub(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.unsubscribed",
        default="OPC UA subscription {id} cancelled.",
        id=payload.get("subscription_id", "?"),
    )


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "unsubscribe").strip().lower()
    output_format = str(args.get("fmt") or "json").strip().lower()

    if action == "list":
        with __import__("threading").Lock():
            subs = list(_SUBSCRIPTIONS.values())
        result = {
            "ok": True,
            "count": len(subs),
            "subscriptions": [
                {
                    "subscription_id": s.get("subscription_id", "?"),
                    "url": s.get("url", ""),
                    "node_id": s.get("node_id", ""),
                    "label": s.get("label", ""),
                    "status": s.get("status", "unknown"),
                }
                for s in subs
            ],
        }
        if output_format == "text":
            return _format_list(result)
        return json.dumps(result, ensure_ascii=False)

    sub_id = str(args.get("subscription_id") or "").strip()
    if not sub_id:
        err = _(
            "err.id_required",
            default="subscription_id is required for action=unsubscribe.",
        )
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    async def _unsubscribe():
        from ..tools.opcua_subscribe_tool import _SUBSCRIPTIONS as subs
        import threading

        with threading.Lock():
            info = subs.pop(sub_id, None)
        if info is None:
            raise ValueError(f"subscription_id '{sub_id}' not found")
        try:
            await info["sub_obj"].delete()
        except Exception:
            pass
        try:
            await info["client"].disconnect()
        except Exception:
            pass
        return sub_id

    loop = None
    import threading

    for t in threading.enumerate():
        if t.name == "opcua-sub":
            try:
                import asyncio

                loop = asyncio.get_event_loop()
            except Exception:
                pass
            break

    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_unsubscribe(), loop)
        try:
            cancelled_id = future.result(timeout=10)
            result = {"ok": True, "subscription_id": cancelled_id}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
    else:
        # Try direct import
        try:
            import asyncio

            asyncio.run(_unsubscribe())
            result = {"ok": True, "subscription_id": sub_id}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}

    if output_format == "text":
        return (
            _format_unsub(result)
            if result.get("ok")
            else f"Error: {result.get('error')}"
        )
    return json.dumps(result, ensure_ascii=False)
