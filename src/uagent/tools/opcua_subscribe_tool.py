from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:opcua_subscribe"

_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {}
_SUBS_LOCK = threading.Lock()
_LOOP: asyncio.AbstractEventLoop | None = None
_THREAD: threading.Thread | None = None
_STOP = threading.Event()


def _ensure_loop():
    global _LOOP, _THREAD
    with _SUBS_LOCK:
        if _LOOP is not None and _LOOP.is_running():
            return _LOOP
        _STOP.clear()
        _LOOP = asyncio.new_event_loop()

        def _run():
            asyncio.set_event_loop(_LOOP)
            _LOOP.run_forever()

        _THREAD = threading.Thread(target=_run, daemon=True, name="opcua-sub")
        _THREAD.start()
        return _LOOP


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "opcua_subscribe",
        "description": _(
            "tool.description",
            default=(
                "Subscribe to data changes on an OPC UA server node. "
                "When the value changes, the LLM is automatically notified. "
                "Returns a subscription_id for later unsubscription."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": _(
                        "param.url.description",
                        default="OPC UA server URL.",
                    ),
                },
                "node_id": {
                    "type": "string",
                    "description": _(
                        "param.node_id.description",
                        default="Node ID to monitor (e.g. 'i=85' or 'ns=2;s=Temperature').",
                    ),
                },
                "label": {
                    "type": "string",
                    "description": _(
                        "param.label.description",
                        default="Human-readable label (e.g. 'ボイラー温度').",
                    ),
                },
                "on_change_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_change_prompt.description",
                        default="Optional prompt for LLM when value changes.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Connection timeout.",
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
            "required": ["url", "node_id"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _format_text(payload: dict[str, Any]) -> str:
    sub = payload.get("subscription") or {}
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    lines = [
        _("msg.subscribed",
          default="OPC UA subscription active: id={id}, {label}",
          id=payload.get("subscription_id", "?"),
          label=sub.get("label") or sub.get("node_id", ""))
    ]
    lines.append(f"  url: {sub.get('url')}")
    lines.append(f"  node: {sub.get('node_id')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    url = str(args.get("url") or "").strip()
    node_id_text = str(args.get("node_id") or "").strip()
    label = str(args.get("label") or "").strip()
    on_change_prompt = str(args.get("on_change_prompt") or "").strip()
    timeout = int(args.get("timeout", 10))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not url:
        err = _("err.url_required", default="url is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)
    if not node_id_text:
        err = _("err.node_id_required", default="node_id is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    sub_id = f"opcua_{hash(url)}_{hash(node_id_text)}_{int(time.time())}"

    async def _subscribe():
        from asyncua import Client

        c = Client(url, timeout=timeout)
        try:
            await c.connect()

            # Parse node ID
            if node_id_text.startswith("i="):
                nid = c.get_node(int(node_id_text[2:]))
            else:
                nid = c.get_node(node_id_text)

            # Create subscription
            sub_handler = _SubHandler(sub_id, label or node_id_text, on_change_prompt)
            sub_obj = await c.create_subscription(200, sub_handler)
            handle = await sub_obj.subscribe_data_change(nid)

            info = {
                "subscription_id": sub_id,
                "url": url,
                "node_id": node_id_text,
                "label": label or node_id_text,
                "on_change_prompt": on_change_prompt,
                "client": c,
                "sub_obj": sub_obj,
                "handle": handle,
                "handler": sub_handler,
                "status": "active",
            }
            with _SUBS_LOCK:
                _SUBSCRIPTIONS[sub_id] = info

            return {"ok": True, "subscription_id": sub_id, "subscription": {
                "url": url, "node_id": node_id_text, "label": label or node_id_text,
                "status": "active",
            }}
        except Exception as e:
            await c.disconnect()
            raise

    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(_subscribe(), loop)
    try:
        result = future.result(timeout=15)
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(payload, ensure_ascii=False)

    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)


class _SubHandler:
    """OPC UA subscription handler that queues events to SchedulerStore."""

    def __init__(self, sub_id: str, label: str, on_change_prompt: str):
        self.sub_id = sub_id
        self.label = label
        self.on_change_prompt = on_change_prompt

    def datachange_notification(self, node, val, data):
        from ..scheduler import SchedulerStore, ScheduleItem, format_iso_datetime, utc_now

        prompt = self.on_change_prompt or f"{self.label}: value changed to {val}"
        item = ScheduleItem(
            id=str(uuid4()),
            type="once",
            at=format_iso_datetime(utc_now() + timedelta(seconds=1)),
            message=f"[OPC UA] {self.label}: {val}",
            llm_prompt=prompt,
            interval_sec=0,
            enabled=True,
        )
        SchedulerStore().add_item(item)

    def event_notification(self, event):
        pass
