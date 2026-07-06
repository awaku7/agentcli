from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .modbus_shared import close_client, create_client
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:modbus_write"

_TOOL_LEVEL = 1

_WRITE_TYPES = [
    "holding",  # Write Single/Multiple Register (0x06/0x10)
    "coil",     # Write Single Coil (0x05)
]

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "modbus_write",
        "description": _(
            "tool.description",
            default=(
                "Write values to a Modbus TCP device. "
                "Supports holding registers (single/multiple) and coils."
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
                        default="Modbus TCP port (default: 502).",
                    ),
                },
                "unit": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 247,
                    "description": _(
                        "param.unit.description",
                        default="Modbus unit ID (default: 1).",
                    ),
                },
                "type": {
                    "type": "string",
                    "enum": _WRITE_TYPES,
                    "default": "holding",
                    "description": _(
                        "param.type.description",
                        default="Register type: holding or coil.",
                    ),
                },
                "address": {
                    "type": "integer",
                    "minimum": 0,
                    "default": 0,
                    "description": _(
                        "param.address.description",
                        default="Starting register address (0-based).",
                    ),
                },
                "values": {
                    "type": "string",
                    "description": _(
                        "param.values.description",
                        default=(
                            "Values to write. "
                            "For holding registers: comma-separated integers (e.g. '100,200,300'). "
                            "For coils: 'on'/'off' or '1'/'0'."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout in seconds.",
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
            "required": ["ip", "values"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _("msg.summary",
             default="Modbus write: {ip} type={t} addr={addr} = {vals}",
             ip=payload.get("target", {}).get("ip", "?"),
             t=payload.get("target", {}).get("type", "?"),
             addr=payload.get("target", {}).get("address", "?"),
             vals=payload.get("values_written", ""))


def run_tool(args: dict[str, Any]) -> str:
    ip = str(args.get("ip") or "").strip()
    port = int(args.get("port", 502))
    unit = int(args.get("unit", 1))
    write_type = str(args.get("type") or "holding").strip().lower()
    address = int(args.get("address", 0))
    values_raw = str(args.get("values") or "").strip()
    timeout = int(args.get("timeout", 5))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip:
        return json.dumps({
            "ok": False,
            "error": _("err.ip_required", default="ip is required.")
        }, ensure_ascii=False)

    if not values_raw:
        return json.dumps({
            "ok": False,
            "error": _("err.values_required", default="values is required.")
        }, ensure_ascii=False)

    if write_type not in _WRITE_TYPES:
        return json.dumps({
            "ok": False,
            "error": _("err.invalid_type",
                       default="Invalid type. Valid: {types}.",
                       types=", ".join(_WRITE_TYPES))
        }, ensure_ascii=False)

    start_time = time.monotonic()
    client = None
    try:
        client = create_client(ip, port, timeout)

        result_str = values_raw
        if write_type == "holding":
            parts = [int(x.strip()) for x in values_raw.split(",") if x.strip()]
            if len(parts) == 1:
                rr = client.write_register(address, parts[0], unit=unit)
            else:
                rr = client.write_registers(address, parts, unit=unit)
            if rr is None or hasattr(rr, 'isError') and rr.isError():
                raise RuntimeError(f"Write holding registers failed: {rr}")
        elif write_type == "coil":
            val = values_raw.strip().lower() in ("1", "true", "on", "active")
            rr = client.write_coil(address, val, unit=unit)
            if rr is None or hasattr(rr, 'isError') and rr.isError():
                raise RuntimeError(f"Write coil failed: {rr}")
            result_str = "on" if val else "off"

        payload = {
            "ok": True,
            "values_written": result_str,
            "target": {
                "ip": ip,
                "port": port,
                "unit": unit,
                "type": write_type,
                "address": address,
            },
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }

        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)

    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": str(exc),
            "target": {
                "ip": ip,
                "port": port,
                "unit": unit,
                "type": write_type,
                "address": address,
            },
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
    finally:
        if client is not None:
            close_client(client)
