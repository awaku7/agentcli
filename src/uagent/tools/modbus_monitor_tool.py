from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .modbus_shared import create_client, close_client
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:modbus_monitor"

_DEFAULT_INTERVAL = 10
_DEFAULT_DURATION = 60

_MONITORS: dict[str, dict[str, Any]] = {}
_MONITORS_LOCK = threading.Lock()


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "modbus_monitor",
        "description": _(
            "tool.description",
            default=(
                "Poll Modbus registers repeatedly and detect changes. "
                "Returns a summary of all detected changes."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Target device IPv4 address.",
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": 502,
                    "description": _(
                        "param.port.description",
                        default="Modbus TCP port.",
                    ),
                },
                "unit": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 247,
                    "description": _(
                        "param.unit.description",
                        default="Modbus unit ID.",
                    ),
                },
                "type": {
                    "type": "string",
                    "enum": ["holding", "input", "coil", "discrete"],
                    "default": "holding",
                    "description": _(
                        "param.type.description",
                        default="Register type to monitor.",
                    ),
                },
                "address": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 0,
                    "description": _(
                        "param.address.description",
                        default="Starting register address.",
                    ),
                },
                "count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 125,
                    "default": 1,
                    "description": _(
                        "param.count.description",
                        default="Number of registers to monitor.",
                    ),
                },
                "interval": {
                    "type": "integer",
                    "default": _DEFAULT_INTERVAL,
                    "minimum": 2,
                    "description": _(
                        "param.interval.description",
                        default="Polling interval in seconds (minimum 2).",
                    ),
                },
                "duration": {
                    "type": "integer",
                    "default": _DEFAULT_DURATION,
                    "minimum": 1,
                    "description": _(
                        "param.duration.description",
                        default="Monitoring duration in seconds.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout per read (seconds).",
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
            "required": ["ip"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _do_read(client: Any, reg_type: str, address: int, count: int, unit: int) -> list[Any] | None:
    try:
        if reg_type == "holding":
            rr = client.read_holding_registers(address, count, unit=unit)
            if rr and not (hasattr(rr, 'isError') and rr.isError()):
                return list(rr.registers)
        elif reg_type == "input":
            rr = client.read_input_registers(address, count, unit=unit)
            if rr and not (hasattr(rr, 'isError') and rr.isError()):
                return list(rr.registers)
        elif reg_type == "coil":
            rr = client.read_coils(address, count, unit=unit)
            if rr and not (hasattr(rr, 'isError') and rr.isError()):
                return [bool(rr.bits[i]) for i in range(min(count, len(rr.bits)))]
        elif reg_type == "discrete":
            rr = client.read_discrete_inputs(address, count, unit=unit)
            if rr and not (hasattr(rr, 'isError') and rr.isError()):
                return [bool(rr.bits[i]) for i in range(min(count, len(rr.bits)))]
    except Exception:
        pass
    return None


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    changes = payload.get("changes") or []
    lines = [
        _("msg.summary",
          default="Modbus monitor: {count} change(s) in {ms} ms.",
          count=len(changes),
          ms=payload.get("elapsed_ms", 0))
    ]
    if not changes:
        lines.append(_("msg.no_changes", default="No changes detected."))
        return "\n".join(lines).strip()
    for idx, c in enumerate(changes, 1):
        lines.append(f"[{idx}] addr={c.get('address')} {c.get('before')} -> {c.get('after')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip = str(args.get("ip") or "").strip()
    port = int(args.get("port", 502))
    unit = int(args.get("unit", 1))
    reg_type = str(args.get("type") or "holding").strip().lower()
    address = int(args.get("address", 0))
    count = min(int(args.get("count", 1)), 125)
    interval = max(2, int(args.get("interval", _DEFAULT_INTERVAL)))
    duration = max(1, int(args.get("duration", _DEFAULT_DURATION)))
    timeout = int(args.get("timeout", 5))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip:
        err = _("err.ip_required", default="ip is required.")
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    start_time = time.monotonic()
    deadline = start_time + duration
    previous: list[Any] | None = None
    all_changes: list[dict[str, Any]] = []
    polls = 0

    while True:
        now = time.monotonic()
        if now >= deadline:
            break

        client = None
        try:
            client = create_client(ip, port, timeout)
            current = _do_read(client, reg_type, address, count, unit)
            polls += 1

            if current is not None and previous is not None:
                for i in range(min(len(previous), len(current))):
                    if previous[i] != current[i]:
                        all_changes.append({
                            "address": address + i,
                            "before": previous[i],
                            "after": current[i],
                            "timestamp": _now_iso(),
                        })
                previous = current
            elif current is not None:
                previous = current
        except Exception:
            pass
        finally:
            if client is not None:
                close_client(client)

        # Wait for next interval
        next_tick = time.monotonic() + interval
        sleep_for = max(0, min(interval, deadline - time.monotonic()))
        if sleep_for > 0:
            time.sleep(sleep_for)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    payload = {
        "ok": True,
        "count": len(all_changes),
        "changes": all_changes,
        "target": {
            "ip": ip,
            "port": port,
            "unit": unit,
            "type": reg_type,
            "address": address,
            "count": count,
        },
        "interval": interval,
        "duration": duration,
        "polls": polls,
        "elapsed_ms": elapsed_ms,
    }

    if output_format == "text":
        return _format_text(payload)
    return json.dumps(payload, ensure_ascii=False)
