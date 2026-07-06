from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

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


def _bac0_import():
    """Dynamically import BAC0 with auto-install."""
    try:
        import BAC0  # type: ignore[import-untyped]
    except ImportError:
        from .._pip_auto import install_with_status as _install_bac0

        if not _install_bac0("BAC0"):
            raise ImportError(
                _(
                    "err.bac0_install",
                    default="BAC0 library could not be installed.",
                )
            )
        import BAC0  # type: ignore[import-untyped]
    return BAC0


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "bacnet_read",
        "description": _(
            "tool.description",
            default=(
                "Read a BACnet property from a device. "
                "Returns the current value and metadata as JSON or text."
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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
    object_instance = _normalize_int(
        args.get("object_instance", 0), 0, 0
    )
    property_name = str(args.get("property_name") or "presentValue").strip()
    output_format = str(args.get("fmt") or "json").strip().lower()

    timeout = _normalize_int(args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1)

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
    BAC0 = _bac0_import()

    bacnet_instance = None
    try:
        bacnet_instance = BAC0.connect()
        if bacnet_instance is None:
            raise RuntimeError("BAC0.connect() returned None")

        if ip_address:
            address = ip_address
        else:
            address = f"device:{device_instance}"

        bacnet_address = f"{address} {object_type} {object_instance} {property_name}"
        raw_value = bacnet_instance.read(bacnet_address)

        value_str = str(raw_value) if raw_value is not None else None
        value_type = type(raw_value).__name__ if raw_value is not None else "NoneType"
        try:
            value_num = float(raw_value) if raw_value is not None else None
        except (ValueError, TypeError):
            value_num = None

        result: dict[str, Any] = {
            "ok": True,
            "value": value_str,
            "value_raw": value_str,
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

        try:
            desc_addr = f"{address} {object_type} {object_instance} description"
            desc_val = bacnet_instance.read(desc_addr)
            if desc_val:
                result["description"] = str(desc_val)
        except Exception:
            pass

        try:
            units_addr = f"{address} {object_type} {object_instance} units"
            units_val = bacnet_instance.read(units_addr)
            if units_val:
                result["units"] = str(units_val)
        except Exception:
            pass

        try:
            sf_addr = f"{address} {object_type} {object_instance} statusFlags"
            sf_val = bacnet_instance.read(sf_addr)
            if sf_val is not None:
                result["status_flags"] = str(sf_val)
        except Exception:
            pass

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
    finally:
        if bacnet_instance is not None:
            try:
                bacnet_instance.disconnect()
            except Exception:
                pass
