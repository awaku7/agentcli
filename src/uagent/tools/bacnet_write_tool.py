from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:bacnet_write"

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
        "name": "bacnet_write",
        "description": _(
            "tool.description",
            default=(
                "Write a value to a BACnet property on a device. "
                "Returns the result as JSON or text."
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
                            "BACnet object type (e.g. 'analogOutput', 'binaryOutput', 'analogValue')."
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
                            "Property name to write (default: 'presentValue')."
                        ),
                    ),
                },
                "value": {
                    "type": "string",
                    "description": _(
                        "param.value.description",
                        default=(
                            "Value to write. "
                            "For analog types use a number string (e.g. '25.0'), "
                            "for binary types use 'active' or 'inactive', "
                            "for multi-state use the state number as string."
                        ),
                    ),
                },
                "priority": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 16,
                    "description": _(
                        "param.priority.description",
                        default=(
                            "Optional BACnet write priority (1-16). "
                            "Lower number = higher priority. "
                            "Default is device-specific."
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
            "required": ["object_type", "object_instance", "value"],
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
            default="BACnet write: {ip_or_dev}/{obj_type}:{obj_inst}.{prop} = {value}",
            ip_or_dev=payload.get("target", {}).get("ip")
            or str(payload.get("target", {}).get("device_instance", "?")),
            obj_type=payload.get("target", {}).get("object_type", "?"),
            obj_inst=payload.get("target", {}).get("object_instance", "?"),
            prop=payload.get("target", {}).get("property_name", "?"),
            value=payload.get("value_written") or "(null)",
        )
    ]
    if payload.get("priority") is not None:
        lines.append(f"  priority: {payload.get('priority')}")
    if payload.get("confirmation"):
        lines.append(f"  confirmation: {payload.get('confirmation')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_address = str(args.get("ip") or "").strip()
    device_instance = args.get("device_instance")
    object_type_raw = str(args.get("object_type") or "").strip()
    object_instance = _normalize_int(
        args.get("object_instance", 0), 0, 0
    )
    property_name = str(args.get("property_name") or "presentValue").strip()
    value_raw = args.get("value")
    priority = args.get("priority")
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

    if value_raw is None or str(value_raw).strip() == "":
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.value_required",
                    default="A value is required for write operation.",
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
        if priority is not None:
            bacnet_address += f" {int(priority)}"

        value_str = str(value_raw).strip()
        bacnet_full = f"{bacnet_address} {value_str}"
        bacnet_instance.write(bacnet_full)

        # Read-back verification (best-effort)
        verify_value = None
        try:
            verify_value = str(bacnet_instance.read(bacnet_address))
        except Exception:
            pass

        result: dict[str, Any] = {
            "ok": True,
            "value_written": value_str,
            "value_verified": verify_value,
            "priority": int(priority) if priority is not None else None,
            "confirmation": "write_sent" if verify_value is None else "verified",
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
                "code": "bacnet_write_failed",
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
