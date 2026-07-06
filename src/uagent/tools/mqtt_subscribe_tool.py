from __future__ import annotations

import json
import threading
import time
from datetime import timedelta
from typing import Any
from uuid import uuid4

from .mqtt_shared import connect, create_client, disconnect, subscribe
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:mqtt_subscribe"

_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {}
_SUBS_LOCK = threading.Lock()


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "mqtt_subscribe",
        "description": _(
            "tool.description",
            default=(
                "Subscribe to an MQTT topic. Messages are automatically "
                "forwarded to the LLM via SchedulerStore."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": _(
                        "param.host.description", default="MQTT broker hostname or IP."
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": 1883,
                    "description": _(
                        "param.port.description", default="MQTT broker port."
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": _(
                        "param.topic.description",
                        default="MQTT topic to subscribe to (wildcards supported).",
                    ),
                },
                "qos": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 2,
                    "description": _(
                        "param.qos.description", default="QoS level (0, 1, 2)."
                    ),
                },
                "label": {
                    "type": "string",
                    "description": _(
                        "param.label.description",
                        default="Human-readable label for this subscription.",
                    ),
                },
                "on_message_prompt": {
                    "type": "string",
                    "description": _(
                        "param.on_message_prompt.description",
                        default="Optional LLM prompt when a message arrives.",
                    ),
                },
                "username": {
                    "type": "string",
                    "description": _(
                        "param.username.description",
                        default="MQTT username (optional).",
                    ),
                },
                "password": {
                    "type": "string",
                    "description": _(
                        "param.password.description",
                        default="MQTT password (optional).",
                    ),
                },
                "use_tls": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.use_tls.description",
                        default="Enable TLS/SSL (MQTTS). Default port becomes 8883.",
                    ),
                },
                "insecure": {
                    "type": "boolean",
                    "default": False,
                    "description": _(
                        "param.insecure.description",
                        default="Skip TLS certificate verification (insecure).",
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description", default="Format: json or text."
                    ),
                },
            },
            "required": ["host", "topic"],
            "additionalProperties": False,
        },
    },
}


def _format_text(payload: dict[str, Any]) -> str:
    sub = payload.get("subscription") or {}
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.subscribed",
        default="MQTT subscribed: {label} [{topic}] @ {host}",
        label=sub.get("label") or sub.get("topic", "?"),
        topic=sub.get("topic", "?"),
        host=sub.get("host", "?"),
    )


def run_tool(args: dict[str, Any]) -> str:
    host = str(args.get("host") or "").strip()
    port = int(args.get("port", 1883))
    topic = str(args.get("topic") or "").strip()
    qos = int(args.get("qos", 0))
    label = str(args.get("label") or "").strip()
    on_message_prompt = str(args.get("on_message_prompt") or "").strip()
    username = str(args.get("username") or "").strip()
    password = str(args.get("password") or "").strip()
    use_tls = bool(args.get("use_tls", False))
    insecure = bool(args.get("insecure", False))
    if use_tls and args.get("port") is None:
        port = 8883
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not host or not topic:
        err = "host and topic are required."
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    sub_id = f"mqtt_{host}_{topic}_{int(time.time())}"

    client = create_client()

    def _on_message(mqtt_topic: str, mqtt_payload: str) -> None:
        """Callback: forward message to SchedulerStore."""
        from ..scheduler import (
            SchedulerStore,
            ScheduleItem,
            format_iso_datetime,
            utc_now,
        )

        lbl = label or mqtt_topic
        prompt = on_message_prompt or f"MQTT message on {mqtt_topic}: {mqtt_payload}"
        item = ScheduleItem(
            id=str(uuid4()),
            type="once",
            at=format_iso_datetime(utc_now() + timedelta(seconds=1)),
            message=f"[MQTT] {lbl}: {mqtt_payload[:200]}",
            llm_prompt=prompt,
            interval_sec=0,
            enabled=True,
        )
        SchedulerStore().add_item(item)

    try:
        connect(
            client,
            host,
            port,
            username=username,
            password=password,
            use_tls=use_tls,
            insecure=insecure,
        )
        subscribe(client, topic, qos=qos, callback=_on_message)

        info = {
            "subscription_id": sub_id,
            "host": host,
            "port": port,
            "topic": topic,
            "qos": qos,
            "label": label or topic,
            "on_message_prompt": on_message_prompt,
            "client": client,
            "status": "active",
        }
        with _SUBS_LOCK:
            _SUBSCRIPTIONS[sub_id] = info

        result = {
            "ok": True,
            "subscription_id": sub_id,
            "subscription": {
                "host": host,
                "topic": topic,
                "qos": qos,
                "label": label or topic,
                "status": "active",
            },
        }

        if output_format == "text":
            return _format_text(result)
        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        disconnect(client)
        err = {"ok": False, "error": str(exc)}
        return (
            json.dumps(err, ensure_ascii=False)
            if output_format != "text"
            else f"Error: {exc}"
        )
