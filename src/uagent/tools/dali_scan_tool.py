from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .dali_shared import _dali_import, create_driver, send_command
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:dali_scan"

_TOOL_LEVEL = 1

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "dali_scan",
        "description": _(
            "tool.description",
            default=(
                "Scan DALI bus for connected lighting devices (addresses 0-63). "
                "Queries each address for status and actual level."
            ),
        ),
            "x_search_terms": _(            "x_search_terms",            default=["dali scan", "dali_scan", "dali", "DALI", "connected", "lighting", "devices", "addresses"],        ),        "x_search_terms_en": ["dali scan", "dali_scan", "dali", "DALI", "connected", "lighting", "devices", "addresses"],
        "parameters": {
            "type": "object",
            "properties": {
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
                        default="DALI driver type. 'auto' tries Tridonic USB, then daliserver.",
                    ),
                },
                "host": {
                    "type": "string",
                    "description": _(
                        "param.host.description",
                        default="daliserver host (required for driver=daliserver).",
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": 55825,
                    "description": _(
                        "param.port.description",
                        default="daliserver TCP port (default: 55825).",
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


def _format_text(payload: dict[str, Any]) -> str:
    devices = payload.get("devices") or []
    lines = [
        _(
            "msg.summary",
            default="DALI scan: {count} device(s) found in {ms} ms.",
            count=len(devices),
            ms=payload.get("elapsed_ms", 0),
        )
    ]
    if not devices:
        lines.append(_("msg.no_devices", default="No DALI devices were found."))
        return "\n".join(lines).strip()
    for idx, dev in enumerate(devices, 1):
        lines.append(
            f"[{idx}] addr={dev.get('address')} level={dev.get('actual_level')} status={dev.get('status')}"
        )
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    driver_type = str(args.get("driver") or "auto").strip().lower()
    host = str(args.get("host") or "").strip()
    port = int(args.get("port", 55825))
    output_format = str(args.get("fmt") or "json").strip().lower()

    start_time = time.monotonic()
    gg, addr, drv = _dali_import()

    driver = None
    try:
        driver = create_driver(driver_type, host=host, port=port)

        devices: list[dict[str, Any]] = []
        for address in range(64):
            try:
                g = addr.GearShort(address)
                # Query status
                status_cmd = gg.QueryStatus(g)
                status_resp = send_command(driver, status_cmd)
                status_val = (
                    bool(status_resp.value)
                    if status_resp and hasattr(status_resp, "value")
                    else None
                )

                # Query actual level
                level_cmd = gg.QueryActualLevel(g)
                level_resp = send_command(driver, level_cmd)
                level_val = (
                    level_resp.value
                    if level_resp and hasattr(level_resp, "value")
                    else None
                )

                if status_val is not None or level_val is not None:
                    devices.append(
                        {
                            "address": address,
                            "status": status_val,
                            "actual_level": level_val,
                            "last_seen": _now_iso(),
                        }
                    )
            except Exception:
                continue

        payload = {
            "ok": True,
            "count": len(devices),
            "devices": devices,
            "driver": driver_type,
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
