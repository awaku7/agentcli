from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .dali_shared import _dali_import, create_driver, send_command
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:dali_write"

_TOOL_LEVEL = 1

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "dali_write",
        "description": _(
            "tool.description",
            default=(
                "Control a DALI lighting device. Supports on/off and dimming (0-254)."
            ),
        ),
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
                        default="DALI device address (0-63), or -1 for broadcast.",
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "dim"],
                    "description": _(
                        "param.action.description",
                        default="Action: on, off, or dim.",
                    ),
                },
                "level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 254,
                    "description": _(
                        "param.level.description",
                        default="Dim level (0-254). Required for action=dim.",
                    ),
                },
                "group": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 15,
                    "description": _(
                        "param.group.description",
                        default="Optional group address (0-15) instead of single address.",
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
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _format_text(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"Error: {payload.get('error', 'unknown')}"
    return _(
        "msg.summary",
        default="DALI {action}: addr={addr} level={level}",
        action=payload.get("action", "?"),
        addr=payload.get("target", {}).get("address", "?"),
        level=payload.get("level", "?"),
    )


def run_tool(args: dict[str, Any]) -> str:
    address = int(args.get("address", -1))
    group = args.get("group")
    action = str(args.get("action") or "").strip().lower()
    level = args.get("level")
    driver_type = str(args.get("driver") or "auto").strip().lower()
    host = str(args.get("host") or "").strip()
    port = int(args.get("port", 55825))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not action or action not in ("on", "off", "dim"):
        return json.dumps(
            {"ok": False, "error": "action must be on, off, or dim."},
            ensure_ascii=False,
        )
    if action == "dim" and level is None:
        return json.dumps(
            {"ok": False, "error": "level is required for dim."}, ensure_ascii=False
        )

    start_time = time.monotonic()
    gg, addr, drv = _dali_import()

    driver = None
    try:
        driver = create_driver(driver_type, host=host, port=port)

        # Resolve destination
        if group is not None:
            destination = addr.GearGroup(int(group))
            address_label = f"group:{group}"
        elif address >= 0:
            destination = addr.GearShort(address)
            address_label = str(address)
        else:
            destination = addr.GearBroadcast()
            address_label = "broadcast"

        # Build command
        if action == "off":
            cmd = gg.Off(destination)
            level_val = 0
        elif action == "on":
            cmd = gg.RecallMaxLevel(destination)
            level_val = 254
        elif action == "dim":
            cmd = gg.DAPC(destination, int(level))
            level_val = int(level)

        send_command(driver, cmd)

        payload = {
            "ok": True,
            "action": action,
            "level": level_val if action == "dim" else level_val,
            "target": {
                "address": address_label,
                "group": group,
                "action": action,
            },
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
