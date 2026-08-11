"""Safe TCP/UDP packet/data sending with dry-run by default."""

from __future__ import annotations

import json
import socket
import time
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)
_MAX_COUNT = 10
_MAX_PAYLOAD = 1400


def _error(code: str, message: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False
    )


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action", "")).lower()
    target = str(args.get("target", "")).strip()
    if action not in {"udp_send", "tcp_send"}:
        return _error(
            "UNSUPPORTED_ACTION", "Only udp_send and tcp_send are implemented."
        )
    if not target:
        return _error("TARGET_REQUIRED", "target is required.")
    try:
        port = int(args.get("port", 0))
        count = int(args.get("count", 1))
        interval = float(args.get("interval", 1.0))
    except (TypeError, ValueError):
        return _error("INVALID_ARGUMENT", "port, count, and interval must be numeric.")
    if port < 1 or port > 65535:
        return _error("INVALID_PORT", "port must be between 1 and 65535.")
    if count < 1 or count > _MAX_COUNT:
        return _error(
            "COUNT_LIMIT_EXCEEDED", f"count must be between 1 and {_MAX_COUNT}."
        )
    if interval < 0 or interval > 60:
        return _error("INVALID_INTERVAL", "interval must be between 0 and 60 seconds.")

    payload = args.get("payload", "")
    if isinstance(payload, str):
        data = payload.encode("utf-8")
    elif isinstance(payload, (bytes, bytearray)):
        data = bytes(payload)
    else:
        return _error("INVALID_PAYLOAD", "payload must be text or bytes.")
    if len(data) > _MAX_PAYLOAD:
        return _error(
            "PAYLOAD_LIMIT_EXCEEDED", f"payload must be at most {_MAX_PAYLOAD} bytes."
        )

    dry_run = bool(args.get("dry_run", True))
    if not dry_run and not bool(args.get("send_confirmed", False)):
        return _error(
            "SEND_CONFIRMATION_REQUIRED",
            "Call human_ask and retry with send_confirmed=true.",
        )
    if dry_run:
        return json.dumps(
            {
                "ok": True,
                "action": action,
                "target": target,
                "port": port,
                "count": count,
                "payload_bytes": len(data),
                "dry_run": True,
                "sent": 0,
            },
            ensure_ascii=False,
        )

    sent = 0
    started = time.perf_counter()
    try:
        if action == "udp_send":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                for index in range(count):
                    sock.sendto(data, (target, port))
                    sent += 1
                    if index + 1 < count and interval:
                        time.sleep(interval)
            finally:
                sock.close()
        else:
            with socket.create_connection((target, port), timeout=5) as sock:
                for index in range(count):
                    sock.sendall(data)
                    sent += 1
                    if index + 1 < count and interval:
                        time.sleep(interval)
    except OSError as exc:
        return json.dumps(
            {
                "ok": False,
                "action": action,
                "target": target,
                "port": port,
                "sent": sent,
                "error": {"code": "SEND_FAILED", "message": str(exc)},
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "ok": True,
            "action": action,
            "target": target,
            "port": port,
            "count": count,
            "payload_bytes": len(data),
            "dry_run": False,
            "sent": sent,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        },
        ensure_ascii=False,
    )


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "packet_send",
        "description": _(
            "tool.description",
            default="Send bounded TCP/UDP data; dry_run is enabled by default.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["udp_send", "tcp_send"]},
                "target": {"type": "string"},
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "payload": {"type": "string"},
                "count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
                "interval": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 60,
                    "default": 1,
                },
                "dry_run": {"type": "boolean", "default": True},
                "send_confirmed": {"type": "boolean", "default": False},
            },
            "required": ["action", "target", "port"],
        },
    },
}
