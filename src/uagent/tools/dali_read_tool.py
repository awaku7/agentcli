from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .dali_shared import _dali_import, create_driver, send_command
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:dali_read"

_TOOL_LEVEL = 1

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "dali_read",
        "description": _(
            "tool.description",
            default=(
                "Read status and level from a DALI lighting device. "
                "Queries the specified address for current state."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["dali read", "dali_read", "dali", "DALI", "level", "lighting"],
        ),
        "x_search_terms_en": [
            "dali read",
            "dali_read",
            "dali",
            "DALI",
            "level",
            "lighting",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 63,
                    "default": 0,
                    "description": _(
                        "param.address.description",
                        default="DALI device address (0-63).",
                    ),
                },
                "driver": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "tridonic",
                        "hasseb",
                        "daliserver",
                        "lunatone",
                        "atxled",
                    ],
                    "default": "auto",
                    "description": _(
                        "param.driver.description",
                        default="DALI driver type.",
                    ),
                },
                "host": {
                    "type": "string",
                    "description": _(
                        "param.host.description",
                        default="daliserver host.",
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": 55825,
                    "description": _(
                        "param.port.description",
                        default="daliserver port.",
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
            "required": ["address"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    dev = payload.get("device", {})
    lines = [
        _(
            "msg.summary",
            default="DALI read: addr={addr} level={level} status={status}",
            addr=dev.get("address", "?"),
            level=dev.get("actual_level", "?"),
            status=dev.get("status", "?"),
        )
    ]
    for k, v in dev.items():
        if k not in ("address", "last_seen") and v is not None:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    address = int(args.get("address", 0))
    driver_type = str(args.get("driver") or "auto").strip().lower()
    host = str(args.get("host") or "").strip()
    port = int(args.get("port", 55825))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if address < 0 or address > 63:
        return json.dumps(
            {"ok": False, "error": "address must be 0-63."}, ensure_ascii=False
        )

    start_time = time.monotonic()
    gg, addr, drv = _dali_import()

    driver = None
    try:
        driver = create_driver(driver_type, host=host, port=port)
        g = addr.GearShort(address)

        status_val = level_val = power_val = min_val = max_val = None

        try:
            r = send_command(driver, gg.QueryStatus(g))
            status_val = bool(r.value) if r and hasattr(r, "value") else None
        except Exception:
            pass
        try:
            r = send_command(driver, gg.QueryActualLevel(g))
            level_val = r.value if r and hasattr(r, "value") else None
        except Exception:
            pass
        try:
            r = send_command(driver, gg.QueryMinLevel(g))
            min_val = r.value if r and hasattr(r, "value") else None
        except Exception:
            pass
        try:
            r = send_command(driver, gg.QueryMaxLevel(g))
            max_val = r.value if r and hasattr(r, "value") else None
        except Exception:
            pass
        try:
            r = send_command(driver, gg.QueryPowerOnLevel(g))
            power_val = r.value if r and hasattr(r, "value") else None
        except Exception:
            pass

        if status_val is None and level_val is None:
            raise RuntimeError(f"No response from address {address}")

        device = {
            "address": address,
            "status": status_val,
            "actual_level": level_val,
            "min_level": min_val,
            "max_level": max_val,
            "power_on_level": power_val,
        }
        payload = {
            "ok": True,
            "device": device,
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }

        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)

    except Exception as exc:
        err = {
            "ok": False,
            "error": str(exc),
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        return (
            json.dumps(err, ensure_ascii=False)
            if output_format != "text"
            else f"Error: {exc}"
        )
    finally:
        if driver is not None and hasattr(driver, "close"):
            try:
                driver.close()
            except Exception:
                pass
