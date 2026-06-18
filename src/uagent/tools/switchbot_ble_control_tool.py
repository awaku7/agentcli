from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:switchbot_ble_control"

_SWITCHBOT_HINTS = {0x0969}
_SWITCHBOT_WRITE_UUID = "cba20002-224d-11e6-9fb8-0002a5d5c51b"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "function": {
        "name": "switchbot_ble_control",
        "description": _(
            "tool.description",
            default=(
                "Control a nearby SwitchBot BLE device and return a JSON or text result."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "devname": {
                    "type": "string",
                    "description": _(
                        "param.devname.description",
                        default=(
                            "Optional device name filter. Matches by exact name or substring."
                        ),
                    ),
                },
                "mac": {
                    "type": "string",
                    "description": _(
                        "param.mac.description",
                        default="MAC address filter.",
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "open", "close", "set_value"],
                    "description": _(
                        "param.action.description",
                        default="Action: on/off/open/close/set_value.",
                    ),
                },
                "value": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": _(
                        "param.value.description",
                        default=(
                            "Optional numeric value for set_value actions. Range: 0-100."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 8,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Scan/connect timeout in seconds.",
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


def _normalize_manufacturer_data(data: dict[int, bytes]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for company_id, payload in data.items():
        if isinstance(payload, (bytes, bytearray)):
            normalized[str(company_id)] = bytes(payload).hex()
    return normalized


def _looks_like_switchbot(name: str | None, manufacturer_data: dict[str, str]) -> bool:
    if name and "switchbot" in name.casefold():
        return True
    return any(key in {str(v) for v in _SWITCHBOT_HINTS} for key in manufacturer_data)


def _matches_filters(
    *,
    address: str,
    name: str | None,
    device_name: str | None,
    mac_address: str | None,
) -> bool:
    if mac_address and address.casefold() != mac_address.casefold():
        return False
    if device_name:
        needle = device_name.casefold()
        haystack = (name or "").casefold()
        if needle not in haystack:
            return False
    return True


async def _scan_once(timeout: int) -> list[dict[str, Any]]:
    from bleak import BleakScanner

    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    result: list[dict[str, Any]] = []
    for device, adv in devices.values():
        manufacturer_data = _normalize_manufacturer_data(
            getattr(adv, "manufacturer_data", {}) or {}
        )
        name = device.name or getattr(adv, "local_name", None) or "Unknown"
        result.append(
            {
                "name": name,
                "address": device.address,
                "rssi": getattr(adv, "rssi", None),
                "device_type": (
                    "switchbot"
                    if _looks_like_switchbot(name, manufacturer_data)
                    else "ble"
                ),
                "service_uuids": list(getattr(adv, "service_uuids", None) or []),
                "manufacturer_data": manufacturer_data,
                "connectable": bool(getattr(adv, "connectable", None)),
                "last_seen": _now_iso(),
            }
        )
    return result


async def _discover_target(
    *,
    timeout: int,
    device_name: str | None,
    mac_address: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    merged: dict[str, dict[str, Any]] = {}

    devices = await _scan_once(timeout)
    for item in devices:
        if not _matches_filters(
            address=str(item.get("address") or ""),
            name=item.get("name"),
            device_name=device_name,
            mac_address=mac_address,
        ):
            continue
        key = str(item.get("address") or item.get("name") or "")
        if not key:
            continue
        current = merged.get(key)
        if current is None:
            merged[key] = item
        else:
            if item.get("rssi") is not None and (
                current.get("rssi") is None or item.get("rssi") > current.get("rssi")
            ):
                current["rssi"] = item.get("rssi")
            current["service_uuids"] = sorted(
                {
                    *(current.get("service_uuids") or []),
                    *(item.get("service_uuids") or []),
                }
            )
            current["manufacturer_data"] = {
                **(current.get("manufacturer_data") or {}),
                **(item.get("manufacturer_data") or {}),
            }
            current["connectable"] = bool(
                current.get("connectable") or item.get("connectable")
            )
            current["last_seen"] = item.get("last_seen") or current.get("last_seen")
            if (
                current.get("device_type") != "switchbot"
                and item.get("device_type") == "switchbot"
            ):
                current["device_type"] = "switchbot"

    items = list(merged.values())
    items.sort(
        key=lambda x: (
            0 if x.get("device_type") == "switchbot" else 1,
            -(int(x["rssi"]) if isinstance(x.get("rssi"), int) else -9999),
            str(x.get("name") or ""),
            str(x.get("address") or ""),
        )
    )

    if mac_address:
        for item in items:
            if str(item.get("address") or "").casefold() == mac_address.casefold():
                return item, None
        return None, {
            "code": "not_found",
            "message": _(
                "err.not_found",
                default="No SwitchBot BLE device matched the provided mac_address.",
                mac_address=mac_address,
            ),
        }

    if device_name:
        needle = device_name.casefold()
        matches = [
            item for item in items if needle in str(item.get("name") or "").casefold()
        ]
        if not matches:
            return None, {
                "code": "not_found",
                "message": _(
                    "err.not_found",
                    default="No SwitchBot BLE device matched the provided device_name.",
                    device_name=device_name,
                ),
            }
        if len(matches) > 1:
            return None, {
                "code": "ambiguous_target",
                "message": _(
                    "err.ambiguous_target",
                    default="Multiple SwitchBot BLE devices matched the provided device_name.",
                    device_name=device_name,
                ),
                "matches": [
                    {"name": item.get("name"), "address": item.get("address")}
                    for item in matches[:10]
                ],
            }
        return matches[0], None

    return None, {
        "code": "invalid_argument",
        "message": _(
            "err.invalid_argument",
            default="Either mac_address or device_name is required.",
        ),
    }


def _build_payload(
    action: str, value: int | None
) -> tuple[bytes | None, int | None, dict[str, Any] | None]:
    normalized = action.casefold().strip()
    if normalized in {"on", "open"}:
        return bytes([0x57, 0x01, 0x01]), 1, None
    if normalized in {"off", "close"}:
        return bytes([0x57, 0x01, 0x00]), 0, None
    if normalized == "set_value":
        if value is None:
            return (
                None,
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.value_required",
                        default="The value field is required for set_value.",
                    ),
                },
            )
        if value < 0 or value > 100:
            return (
                None,
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.invalid_value_range",
                        default="The value field must be between 0 and 100.",
                    ),
                },
            )
        return bytes([0x57, 0x01, int(value)]), int(value), None
    return (
        None,
        None,
        {
            "code": "invalid_argument",
            "message": _(
                "err.unknown_action",
                default="Error: Unknown action '{action}'.",
                action=action,
            ),
        },
    )


async def _write_control(
    *,
    address: str,
    timeout: int,
    payload: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]], str, bool]:
    from bleak import BleakClient

    writable_candidates: list[dict[str, Any]] = []
    async with BleakClient(address, timeout=timeout) as client:
        services = getattr(client, "services", None)
        if services is None:
            try:
                services = await client.get_services()  # type: ignore[attr-defined]
            except Exception:
                services = None

        chosen_char = None
        if services is not None:
            for service in services:
                for char in getattr(service, "characteristics", []) or []:
                    properties = [
                        str(p).lower() for p in (getattr(char, "properties", []) or [])
                    ]
                    char_uuid = str(getattr(char, "uuid", ""))
                    if not properties:
                        continue
                    if "write" in properties or "write-without-response" in properties:
                        writable_candidates.append(
                            {
                                "uuid": char_uuid,
                                "properties": list(
                                    getattr(char, "properties", []) or []
                                ),
                                "service_uuid": str(getattr(service, "uuid", "")),
                            }
                        )
                        if char_uuid.casefold() == _SWITCHBOT_WRITE_UUID:
                            chosen_char = char_uuid
                    if (
                        chosen_char is None
                        and char_uuid.casefold() == _SWITCHBOT_WRITE_UUID
                    ):
                        chosen_char = char_uuid

        if chosen_char is None and writable_candidates:
            chosen_char = writable_candidates[0]["uuid"]

        if chosen_char is None:
            raise RuntimeError(
                _(
                    "err.no_writable_characteristic",
                    default=(
                        "The device did not expose a writable GATT characteristic suitable for control."
                    ),
                )
            )

        write_with_response = True
        if services is not None:
            for service in services:
                for char in getattr(service, "characteristics", []) or []:
                    if (
                        str(getattr(char, "uuid", "")).casefold()
                        == chosen_char.casefold()
                    ):
                        props = {
                            str(p).lower()
                            for p in (getattr(char, "properties", []) or [])
                        }
                        write_with_response = "write" in props
                        break
                else:
                    continue
                break

        await client.write_gatt_char(chosen_char, payload, response=write_with_response)
        return (
            {
                "connected": True,
                "characteristic_uuid": chosen_char,
                "write_with_response": write_with_response,
            },
            writable_candidates,
            chosen_char,
            write_with_response,
        )


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    device = result.get("device", {}) or {}
    status = result.get("status", {}) or {}
    lines = [
        _(
            "msg.summary",
            default="SwitchBot BLE control completed: {action} on {device_name} ({device_id}).",
            action=status.get("action") or "(unknown)",
            device_name=device.get("devname") or device.get("name") or "(unknown)",
            device_id=device.get("dev") or device.get("address") or "(unknown)",
        ),
        f"Address: {device.get('address') or '-'}",
        f"Device type: {device.get('device_type') or '-'}",
        f"Payload: {status.get('payload_hex') or '-'}",
        f"Characteristic: {status.get('characteristic_uuid') or '-'}",
        f"Write response: {status.get('write_with_response')}",
    ]
    if status.get("value") is not None:
        lines.append(f"Value: {status.get('value')}")
    lines.append(f"Elapsed ms: {result.get('elapsed_ms')}")
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    device_name = args.get("devname")
    mac_address = args.get("mac")
    action = str(args.get("action") or "").strip()
    raw_value = args.get("value")

    try:
        timeout = int(args.get("timeout", 8))
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_numeric",
                    default="Timeout must be an integer.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if timeout <= 0:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_range",
                    default="Timeout must be greater than 0.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    try:
        value = None if raw_value is None else int(raw_value)
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_value_type",
                    default="The value field must be an integer.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    try:
        import bleak  # noqa: F401
    except ImportError:
        payload = {
            "ok": False,
            "error": {
                "code": "bleak_missing",
                "message": _(
                    "err.bleak_missing",
                    default=(
                        "Error: 'bleak' library is not installed. Please install it using:\npip install bleak"
                    ),
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    started = time.perf_counter()
    try:
        device, err = asyncio.run(
            _discover_target(
                timeout=timeout,
                device_name=str(device_name) if device_name else None,
                mac_address=str(mac_address) if mac_address else None,
            )
        )
        if err is not None or device is None:
            payload = {
                "ok": False,
                "error": err or {"code": "not_found", "message": "Not found."},
            }
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        if not _looks_like_switchbot(
            device.get("name"), dict(device.get("manufacturer_data") or {})
        ):
            payload = {
                "ok": False,
                "error": {
                    "code": "unsupported_device",
                    "message": _(
                        "err.unsupported_device",
                        default="The matched device does not look like a SwitchBot BLE device.",
                    ),
                },
                "device": device,
            }
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        payload_bytes, normalized_value, build_err = _build_payload(action, value)
        if build_err is not None or payload_bytes is None:
            payload = {
                "ok": False,
                "error": build_err
                or {"code": "invalid_argument", "message": "Invalid action."},
            }
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        status, capabilities, characteristic_uuid, write_with_response = asyncio.run(
            _write_control(
                address=str(device.get("address") or ""),
                timeout=timeout,
                payload=payload_bytes,
            )
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "ok": True,
            "device": {
                "dev": device.get("address"),
                "devname": device.get("name"),
                "device_type": device.get("device_type"),
                "hub_id": None,
                "online": True,
                "battery": None,
                "reachable": True,
                "address": device.get("address"),
                "rssi": device.get("rssi"),
                "service_uuids": device.get("service_uuids") or [],
                "manufacturer_data": device.get("manufacturer_data") or {},
                "connectable": device.get("connectable"),
                "last_seen": device.get("last_seen"),
            },
            "status": {
                **status,
                "action": action,
                "value": normalized_value,
                "payload_hex": payload_bytes.hex(),
            },
            "capabilities": capabilities,
            "elapsed_ms": elapsed_ms,
            "last_updated": _now_iso(),
            "account": {
                "source": "local_ble",
                "authenticated": True,
            },
        }
        if output_format == "text":
            return _format_text(result)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        err_msg = str(exc)
        if "timed out" in err_msg.lower():
            payload = {
                "ok": False,
                "error": {
                    "code": "timeout",
                    "message": err_msg,
                },
            }
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        if sys.platform.startswith("linux"):
            if (
                "Permission" in err_msg
                or "AccessDenied" in err_msg
                or "dbus" in err_msg.lower()
                or "notready" in err_msg.lower()
            ):
                payload = {
                    "ok": False,
                    "error": {
                        "code": "network_error",
                        "message": _(
                            "err.linux_permission",
                            default=(
                                "Error during BLE operation: {err_msg}\n\n[Linux/Raspberry Pi Permission Guide]\nYou might lack permissions to access the Bluetooth socket. Try one of the following:\n1. Add your user to the bluetooth group (recommended):\n   sudo usermod -aG bluetooth $USER\n   (Requires restart or re-login)\n2. Grant permissions directly to the Python binary:\n   sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))"
                            ),
                            err_msg=err_msg,
                        ),
                    },
                }
                return (
                    json.dumps(payload, ensure_ascii=False, indent=2)
                    if output_format == "text"
                    else json.dumps(payload, ensure_ascii=False)
                )
        elif sys.platform == "darwin":
            if (
                "CoreBluetooth" in err_msg
                or "permission" in err_msg.lower()
                or "auth" in err_msg.lower()
            ):
                payload = {
                    "ok": False,
                    "error": {
                        "code": "network_error",
                        "message": _(
                            "err.macos_permission",
                            default=(
                                "Error during BLE operation: {err_msg}\n\n[macOS Permission Guide]\nBluetooth access might have been denied by macOS security restrictions.\nPlease open 'System Settings > Privacy & Security > Bluetooth' and ensure your terminal, VS Code, or Python process is allowed to access Bluetooth."
                            ),
                            err_msg=err_msg,
                        ),
                    },
                }
                return (
                    json.dumps(payload, ensure_ascii=False, indent=2)
                    if output_format == "text"
                    else json.dumps(payload, ensure_ascii=False)
                )

        payload = {
            "ok": False,
            "error": {
                "code": "request_failed",
                "message": _(
                    "err.operation_failed",
                    default="Error during BLE operation: {err_msg}",
                    err_msg=err_msg,
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
