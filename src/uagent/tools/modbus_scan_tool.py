from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:modbus_scan"

_DEFAULT_TIMEOUT = 3
_DEFAULT_PORT = 502


def _modbus_import():
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        from .._pip_auto import install_with_status as _install_mb

        if not _install_mb("pymodbus"):
            raise ImportError("pymodbus library could not be installed.")
        from pymodbus.client import ModbusTcpClient
    return ModbusTcpClient


def _pymodbus_version() -> str:
    try:
        import pymodbus

        return getattr(pymodbus, "__version__", "unknown")
    except Exception:
        return "unknown"


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "modbus_scan",
        "description": _(
            "tool.description",
            default=(
                "Scan Modbus TCP devices on the local network. "
                "Probes IP addresses and unit IDs to discover Modbus devices."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ip_range": {
                    "type": "string",
                    "description": _(
                        "param.ip_range.description",
                        default=(
                            "IP range to scan (e.g. '192.168.1.1-254' or '192.168.1.0/24'). "
                            "Required. If omitted, typical local subnets are tried."
                        ),
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": _DEFAULT_PORT,
                    "description": _(
                        "param.port.description",
                        default="Modbus TCP port (default: 502).",
                    ),
                },
                "unit_start": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 247,
                    "description": _(
                        "param.unit_start.description",
                        default="Starting unit ID (default: 1).",
                    ),
                },
                "unit_end": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 247,
                    "description": _(
                        "param.unit_end.description",
                        default="Ending unit ID (default: 10).",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout per connection attempt (seconds).",
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_ip_range(text: str) -> list[str]:
    """Parse an IP range string into a list of IP addresses."""
    text = text.strip()
    ips: list[str] = []

    # CIDR notation
    if "/" in text:
        try:
            import ipaddress

            network = ipaddress.ip_network(text, strict=False)
            for host in network.hosts():
                ips.append(str(host))
            return ips
        except Exception:
            pass

    # Range notation: 192.168.1.1-254
    if "-" in text:
        parts = text.rsplit(".", 1)
        if len(parts) == 2:
            base = parts[0]
            range_part = parts[1]
            if "-" in range_part:
                try:
                    start_s, end_s = range_part.split("-", 1)
                    start = int(start_s.strip())
                    end = int(end_s.strip())
                    for i in range(start, end + 1):
                        ips.append(f"{base}.{i}")
                    return ips
                except Exception:
                    pass

    # Single IP
    try:
        socket.inet_aton(text)
        ips.append(text)
    except Exception:
        pass

    return ips


def _format_text(payload: dict[str, Any]) -> str:
    devices = payload.get("devices") or []
    lines = [
        _(
            "msg.summary",
            default="Modbus scan completed: {count} device(s) found in {ms} ms.",
            count=len(devices),
            ms=payload.get("elapsed_ms", 0),
        )
    ]
    lines.append(f"Scanned IPs: {payload.get('ips_scanned', 0)}")
    lines.append(f"Unit range: {payload.get('unit_start')}-{payload.get('unit_end')}")
    lines.append("")

    if not devices:
        lines.append(_("msg.no_devices", default="No Modbus devices were found."))
        return "\n".join(lines).strip()

    for idx, dev in enumerate(devices, 1):
        lines.append(
            f"[{idx}] {dev.get('ip')}:{dev.get('port')} unit={dev.get('unit_id')}"
        )
        if dev.get("vendor"):
            lines.append(f"  vendor: {dev.get('vendor')}")
        if dev.get("model"):
            lines.append(f"  model: {dev.get('model')}")
        lines.append("")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_range = str(args.get("ip_range") or "").strip()
    port = int(args.get("port", _DEFAULT_PORT))
    unit_start = int(args.get("unit_start", 1))
    unit_end = int(args.get("unit_end", 10))
    timeout = int(args.get("timeout", _DEFAULT_TIMEOUT))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip_range:
        err = _(
            "err.ip_range_required",
            default="ip_range is required (e.g. '192.168.1.1-254' or '192.168.1.0/24').",
        )
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    ips = _parse_ip_range(ip_range)
    if not ips:
        err = _(
            "err.invalid_ip_range",
            default="Could not parse ip_range: {text}",
            text=ip_range,
        )
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    if len(ips) > 255:
        err = _(
            "err.too_many_ips",
            default="Too many IPs ({count}). Limit to 255.",
            count=len(ips),
        )
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    start_time = time.monotonic()
    ModbusTcpClient = _modbus_import()
    devices: list[dict[str, Any]] = []

    for ip in ips:
        for unit_id in range(max(1, unit_start), min(247, unit_end) + 1):
            client = None
            try:
                client = ModbusTcpClient(ip, port=port, timeout=timeout)
                if not client.connect():
                    continue

                # Try reading coil 0 or holding register 0
                rr = client.read_holding_registers(0, 1, unit=unit_id)
                if rr is None or hasattr(rr, "isError") and rr.isError():
                    continue

                devices.append(
                    {
                        "ip": ip,
                        "port": port,
                        "unit_id": unit_id,
                        "vendor": None,
                        "model": None,
                        "first_register": rr.registers[0]
                        if hasattr(rr, "registers") and rr.registers
                        else None,
                        "last_seen": _now_iso(),
                    }
                )
                break  # Found this IP, move to next IP
            except Exception:
                continue
            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception:
                        pass

    payload = {
        "ok": True,
        "count": len(devices),
        "devices": devices,
        "ip_range": ip_range,
        "ips_scanned": len(ips),
        "unit_start": max(1, unit_start),
        "unit_end": min(247, unit_end),
        "elapsed_ms": int((time.monotonic() - start_time) * 1000),
    }

    if output_format == "text":
        return _format_text(payload)
    return json.dumps(payload, ensure_ascii=False)
