from __future__ import annotations

import json
import time
from typing import Any

from .i18n_helper import make_tool_translator
from . import bacnet_shared

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:bacnet_read"

_DEFAULT_TIMEOUT = 4

_VALID_OBJECT_TYPES = [
    "analogInput",
    "analogOutput",
    "analogValue",
    "binaryInput",
    "binaryOutput",
    "binaryValue",
    "multiStateInput",
    "multiStateOutput",
    "multiStateValue",
    "device",
    "accumulator",
    "loop",
    "schedule",
    "notificationClass",
    "trendLog",
]


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "bacnet_read",
        "description": _(
            "tool.description",
            default=(
                "Read a BACnet property from a device. "
                "Returns the current value and metadata as JSON or text."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["bacnet read", "bacnet_read", "bacnet", "BACNET", "returns"],
        ),
        "x_search_terms_en": [
            "bacnet read",
            "bacnet_read",
            "bacnet",
            "BACNET",
            "returns",
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
                "device_instance": {
                    "type": "integer",
                    "description": _(
                        "param.device_instance.description",
                        default=(
                            "BACnet device instance number (alternative to ip). "
                            "Used if ip is not provided."
                        ),
                    ),
                },
                "object_type": {
                    "type": "string",
                    "enum": _VALID_OBJECT_TYPES,
                    "description": _(
                        "param.object_type.description",
                        default=(
                            "BACnet object type (e.g. 'analogInput', 'binaryOutput', 'analogValue')."
                        ),
                    ),
                },
                "object_instance": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.object_instance.description",
                        default="BACnet object instance number.",
                    ),
                },
                "property_name": {
                    "type": "string",
                    "default": "presentValue",
                    "description": _(
                        "param.property_name.description",
                        default=(
                            "Property name to read (default: 'presentValue'). "
                            "Common: presentValue, description, units, statusFlags, objectName."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
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
            "required": ["object_type", "object_instance"],
            "additionalProperties": False,
        },
    },
}


def _normalize_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        result = int(value)
    except Exception:
        return default
    if result < minimum:
        return default if default >= minimum else minimum
    return result


def _normalize_object_type(raw: str | None) -> str | None:
    if not raw:
        return None
    text = str(raw).strip().lower()
    for valid in _VALID_OBJECT_TYPES:
        if valid.lower() == text:
            return valid
    return None


def _format_text(payload: dict[str, Any]) -> str:
    lines = [
        _(
            "msg.summary",
            default="BACnet read: {ip_or_dev}/{obj_type}:{obj_inst}.{prop} = {value}",
            ip_or_dev=payload.get("target", {}).get("ip")
            or str(payload.get("target", {}).get("device_instance", "?")),
            obj_type=payload.get("target", {}).get("object_type", "?"),
            obj_inst=payload.get("target", {}).get("object_instance", "?"),
            prop=payload.get("target", {}).get("property_name", "?"),
            value=payload.get("value") or "(null)",
        )
    ]
    if payload.get("units"):
        lines.append(f"  units: {payload.get('units')}")
    if payload.get("status_flags"):
        lines.append(f"  status_flags: {payload.get('status_flags')}")
    if payload.get("description"):
        lines.append(f"  description: {payload.get('description')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_address = str(args.get("ip") or "").strip()
    device_instance = args.get("device_instance")
    object_type_raw = str(args.get("object_type") or "").strip()
    object_instance = _normalize_int(args.get("object_instance", 0), 0, 0)
    property_name = str(args.get("property_name") or "presentValue").strip()
    timeout = _normalize_int(args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1)
    output_format = str(args.get("fmt") or "json").strip().lower()

    object_type = _normalize_object_type(object_type_raw)
    if not object_type:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_object_type",
                    default="Invalid object_type. Valid: {types}.",
                    types=", ".join(_VALID_OBJECT_TYPES),
                ),
            },
        }
        return (
            f"Error: {payload['error']['message']}"
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if not ip_address and device_instance is None:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.ip_or_device_required",
                    default="Either ip or device_instance is required.",
                ),
            },
        }
        return (
            f"Error: {payload['error']['message']}"
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    start_time = time.monotonic()

    try:
        bacnet_shared._bac0_import()

        if ip_address:
            address = ip_address
        else:
            address = f"device:{device_instance}"

        bacnet_address = f"{address} {object_type} {object_instance} {property_name}"

        async def _do_read(lite: Any) -> Any:
            return await bacnet_shared.read_property(
                lite, bacnet_address, timeout=timeout
            )

        raw_value = bacnet_shared.run_on_bac0_loop(
            _do_read,
            ip=None,
            timeout=float(timeout) + 10.0,
            keep_alive=False,
        )

        value_str = str(raw_value) if raw_value is not None else None
        value_type = type(raw_value).__name__ if raw_value is not None else "NoneType"
        try:
            value_num = float(raw_value) if raw_value is not None else None
        except (ValueError, TypeError):
            value_num = None

        result: dict[str, Any] = {
            "ok": True,
            "value": value_str,
            "value_type": value_type,
            "value_numeric": value_num,
            "units": None,
            "status_flags": None,
            "description": None,
            "target": {
                "ip": ip_address or None,
                "device_instance": device_instance,
                "object_type": object_type,
                "object_instance": object_instance,
                "property_name": property_name,
            },
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }

        if output_format == "text":
            return _format_text(result)
        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": {
                "code": "bacnet_read_failed",
                "message": str(exc),
            },
            "target": {
                "ip": ip_address or None,
                "device_instance": device_instance,
                "object_type": object_type,
                "object_instance": object_instance,
                "property_name": property_name,
            },
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
