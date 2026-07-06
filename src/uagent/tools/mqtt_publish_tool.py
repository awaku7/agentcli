from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .mqtt_shared import connect, create_client, disconnect, publish
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:mqtt_publish"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "mqtt_publish",
        "description": _(
            "tool.description",
            default="Publish a message to an MQTT topic. Connects, publishes, and disconnects.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": _("param.host.description", default="MQTT broker hostname or IP."),
                },
                "port": {
                    "type": "integer", "default": 1883,
                    "description": _("param.port.description", default="MQTT broker port (default: 1883)."),
                },
                "topic": {
                    "type": "string",
                    "description": _("param.topic.description", default="MQTT topic to publish to."),
                },
                "payload": {
                    "type": "string",
                    "description": _("param.payload.description", default="Message payload."),
                },
                "qos": {
                    "type": "integer", "default": 0, "minimum": 0, "maximum": 2,
                    "description": _("param.qos.description", default="QoS level (0, 1, 2)."),
                },
                "retain": {
                    "type": "boolean", "default": False,
                    "description": _("param.retain.description", default="Retain message on broker."),
                },
                "username": {
                    "type": "string",
                    "description": _("param.username.description", default="MQTT username (optional)."),
                },
                "password": {
                    "type": "string",
                    "description": _("param.password.description", default="MQTT password (optional)."),
                },
                "use_tls": {
                    "type": "boolean", "default": False,
                    "description": _("param.use_tls.description", default="Enable TLS/SSL (MQTTS). Default port becomes 8883."),
                },
                "insecure": {
                    "type": "boolean", "default": False,
                    "description": _("param.insecure.description", default="Skip TLS certificate verification (insecure)."),
                },
                "fmt": {
                    "type": "string", "enum": ["json", "text"], "default": "json",
                    "description": _("param.fmt.description", default="Format: json or text."),
                },
            },
            "required": ["host", "topic", "payload"],
            "additionalProperties": False,
        },
    },
}


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _("msg.sent", default="MQTT published: {topic} = {payload} [{qos}]",
             topic=payload.get("topic", "?"), payload=payload.get("payload", ""), qos=payload.get("qos", 0))


def run_tool(args: dict[str, Any]) -> str:
    host = str(args.get("host") or "").strip()
    port = int(args.get("port", 1883))
    topic = str(args.get("topic") or "").strip()
    payload = str(args.get("payload") or "").strip()
    qos = int(args.get("qos", 0))
    retain = bool(args.get("retain", False))
    username = str(args.get("username") or "").strip()
    password = str(args.get("password") or "").strip()
    use_tls = bool(args.get("use_tls", False))
    insecure = bool(args.get("insecure", False))
    if use_tls and args.get("port") is None:
        port = 8883
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not host or not topic or not payload:
        return json.dumps({"ok": False, "error": "host, topic, payload are required."}, ensure_ascii=False)

    start = time.monotonic()
    client = None
    try:
        client = create_client()
        connect(client, host, port, username=username, password=password,
                 use_tls=use_tls, insecure=insecure)
        result = publish(client, topic, payload, qos=qos, retain=retain)
        result["elapsed_ms"] = int((time.monotonic() - start) * 1000)
        return json.dumps(result, ensure_ascii=False) if output_format != "text" else _format_text(result)
    except Exception as exc:
        err = {"ok": False, "error": str(exc), "elapsed_ms": int((time.monotonic() - start) * 1000)}
        return json.dumps(err, ensure_ascii=False) if output_format != "text" else f"Error: {exc}"
    finally:
        if client:
            disconnect(client)
