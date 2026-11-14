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
    # Only the trusted host dispatcher can approve real packet transmission.
    # Model-supplied send_confirmed flags do not authorize network sends.
    if not dry_run:
        from .tool_confirmation import dispatcher_approved

        if not dispatcher_approved("packet_send"):
            return _error("SEND_CONFIRMATION_REQUIRED", "Host approval required.")
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
    "tool_level": 1,
    "x_parallel_safe": False,
    "function": {
        "name": "packet_send",
        "description": _(
            "tool.description",
            default="Send bounded TCP/UDP data; dry_run is enabled by default.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "packet send",
                "udp send",
                "tcp send",
                "network test",
            ],
        ),
        "x_search_terms_en": [
            "packet send",
            "udp send",
            "tcp send",
            "network test",
        ],
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
            },
            "required": ["action", "target", "port"],
        },
    },
}


_SEND_ACTIONS = ["udp_send", "tcp_send"]
_SEND_ACTION_LABELS_EN = ["Send UDP data", "Send TCP data"]


def describe(args: dict[str, Any]) -> str:
    """Summarize packet transmission without echoing the payload."""

    args = args or {}
    action = str(args.get("action") or "")
    labels = _("describe.action_labels", default=_SEND_ACTION_LABELS_EN)
    if not isinstance(labels, list) or len(labels) != len(_SEND_ACTIONS):
        labels = _SEND_ACTION_LABELS_EN
    method = dict(zip(_SEND_ACTIONS, labels)).get(action, action or "Send network data")

    dry_run = args.get("dry_run", True)
    is_dry_run = bool(dry_run) if dry_run is not None else True
    if is_dry_run:
        intent = str(
            _(
                "param.dry_run.description",
                default="Preview only; no data will be sent.",
            )
        )
    else:
        intent = str(
            _(
                "tool.description",
                default="Send bounded TCP/UDP data.",
            )
        )
    payload = args.get("payload", "")
    if isinstance(payload, str):
        payload_bytes = len(payload.encode("utf-8"))
    elif isinstance(payload, (bytes, bytearray)):
        payload_bytes = len(payload)
    else:
        payload_bytes = 0

    return str(
        _(
            "describe.summary",
            default=(
                "%(intent)s: %(method)s to %(target)s:%(port)s "
                "(%(count)s send(s), %(payload_bytes)s payload bytes)."
            ),
            intent=intent,
            method=method,
            target=str(args.get("target") or "<unknown target>"),
            port=args.get("port", "?"),
            count=args.get("count", 1),
            payload_bytes=payload_bytes,
        )
    )


TOOL_DESCRIBER = describe
