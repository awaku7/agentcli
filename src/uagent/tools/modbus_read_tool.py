from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .modbus_shared import close_client, create_client
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:modbus_read"

_TOOL_LEVEL = 1

_REGISTER_TYPES = [
    "holding",  # Holding Registers (function code 0x03)
    "input",  # Input Registers (function code 0x04)
    "coil",  # Coils (function code 0x01)
    "discrete",  # Discrete Inputs (function code 0x02)
]

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "modbus_read",
        "description": _(
            "tool.description",
            default=(
                "Read Modbus TCP registers from a device. "
                "Supports holding registers, input registers, coils, and discrete inputs."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "modbus read",
                "modbus_read",
                "modbus",
                "MODBUS",
                "registers",
                "supports",
            ],
        ),
        "x_search_terms_en": [
            "modbus read",
            "modbus_read",
            "modbus",
            "MODBUS",
            "registers",
            "supports",
        ],
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
                    "enum": _REGISTER_TYPES,
                    "default": "holding",
                    "description": _(
                        "param.type.description",
                        default="Register type: holding, input, coil, or discrete.",
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
                "count": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 125,
                    "default": 1,
                    "description": _(
                        "param.count.description",
                        default="Number of registers to read (max 125 for holding/input, 2000 for coils/discrete).",
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
            "required": ["ip"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    lines = [
        _(
            "msg.summary",
            default="Modbus read: {ip} type={t} addr={addr} count={count}",
            ip=payload.get("target", {}).get("ip", "?"),
            t=payload.get("target", {}).get("type", "?"),
            addr=payload.get("target", {}).get("address", "?"),
            count=len(payload.get("values", [])),
        )
    ]
    values = payload.get("values", [])
    for i, v in enumerate(values):
        lines.append(f"  [{payload.get('target', {}).get('address', 0) + i}] = {v}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip = str(args.get("ip") or "").strip()
    port = int(args.get("port", 502))
    unit = int(args.get("unit", 1))
    reg_type = str(args.get("type") or "holding").strip().lower()
    address = int(args.get("address", 0))
    count = min(int(args.get("count", 1)), 125)
    timeout = int(args.get("timeout", 5))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip:
        return json.dumps(
            {"ok": False, "error": _("err.ip_required", default="ip is required.")},
            ensure_ascii=False,
        )

    if reg_type not in _REGISTER_TYPES:
        return json.dumps(
            {
                "ok": False,
                "error": _(
                    "err.invalid_type",
                    default="Invalid type. Valid: {types}.",
                    types=", ".join(_REGISTER_TYPES),
                ),
            },
            ensure_ascii=False,
        )

    start_time = time.monotonic()
    client = None
    try:
        client = create_client(ip, port, timeout)

        values: list[Any] = []
        if reg_type == "holding":
            rr = client.read_holding_registers(address, count, unit=unit)
            if rr is None or hasattr(rr, "isError") and rr.isError():
                raise RuntimeError(f"Read holding registers failed: {rr}")
            values = list(rr.registers)
        elif reg_type == "input":
            rr = client.read_input_registers(address, count, unit=unit)
            if rr is None or hasattr(rr, "isError") and rr.isError():
                raise RuntimeError(f"Read input registers failed: {rr}")
            values = list(rr.registers)
        elif reg_type == "coil":
            rr = client.read_coils(address, count, unit=unit)
            if rr is None or hasattr(rr, "isError") and rr.isError():
                raise RuntimeError(f"Read coils failed: {rr}")
            values = [bool(rr.bits[i]) for i in range(min(count, len(rr.bits)))]
        elif reg_type == "discrete":
            rr = client.read_discrete_inputs(address, count, unit=unit)
            if rr is None or hasattr(rr, "isError") and rr.isError():
                raise RuntimeError(f"Read discrete inputs failed: {rr}")
            values = [bool(rr.bits[i]) for i in range(min(count, len(rr.bits)))]

        payload = {
            "ok": True,
            "values": values,
            "target": {
                "ip": ip,
                "port": port,
                "unit": unit,
                "type": reg_type,
                "address": address,
                "count": count,
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
                "type": reg_type,
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
