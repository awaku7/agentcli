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
STATUS_LABEL = "tool:switchbot_ble_status"

_SWITCHBOT_HINTS = {0x0969}
_BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "switchbot_ble_status",
        "description": _(
            "tool.description",
            default=(
                "Read the status of a nearby SwitchBot BLE device and return a JSON or text summary."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default=(
                            "Optional local BLE adapter/interface name to bind to."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 8,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default=("Scan/connect timeout in seconds."),
                    ),
                },
                "retry": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 1,
                    "description": _(
                        "param.retry.description",
                        default=("How many BLE scan rounds to run before connecting."),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default=(
                            "Max characteristics (0 = unlimited)."
                        ),
                    ),
                },
                "device_name": {
                    "type": "string",
                    "description": _(
                        "param.device_name.description",
                        default=(
                            "Device name filter."
                        ),
                    ),
                },
                "mac_address": {
                    "type": "string",
                    "description": _(
                        "param.mac_address.description",
                        default="MAC address filter.",
                    ),
                },
                "service_uuid": {
                    "type": "string",
                    "description": _(
                        "param.service_uuid.description",
                        default=("Optional GATT service UUID filter."),
                    ),
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.output_format.description",
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


def _normalize_manufacturer_data(data: dict[int, bytes]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for company_id, payload in data.items():
        if isinstance(payload, (bytes, bytearray)):
            normalized[str(company_id)] = bytes(payload).hex()
    return normalized


def _looks_like_switchbot(name: str | None, manufacturer_data: dict[str, str]) -> bool:
    if name and "switchbot" in name.casefold():
        return True
    return any(
        str(key) in {str(v) for v in _SWITCHBOT_HINTS} for key in manufacturer_data
    )


def _matches_filters(
    *,
    address: str,
    name: str | None,
    service_uuids: list[str],
    device_name: str | None,
    mac_address: str | None,
    service_uuid: str | None,
) -> bool:
    if mac_address and address.casefold() != mac_address.casefold():
        return False
    if device_name:
        needle = device_name.casefold()
        haystack = (name or "").casefold()
        if needle not in haystack:
            return False
    if service_uuid:
        target = service_uuid.casefold()
        if target not in {u.casefold() for u in service_uuids}:
            return False
    return True


async def _scan_once(timeout: int, interface: str | None) -> list[dict[str, Any]]:
    from bleak import BleakScanner

    kwargs: dict[str, Any] = {"timeout": timeout, "return_adv": True}
    if interface:
        kwargs["adapter"] = interface
    try:
        devices = await BleakScanner.discover(**kwargs)
    except TypeError:
        kwargs.pop("adapter", None)
        devices = await BleakScanner.discover(**kwargs)

    result: list[dict[str, Any]] = []
    for device, adv in devices.values():
        manufacturer_data = _normalize_manufacturer_data(
            getattr(adv, "manufacturer_data", {}) or {}
        )
        service_uuids = list(getattr(adv, "service_uuids", None) or [])
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
                "service_uuids": service_uuids,
                "manufacturer_data": manufacturer_data,
                "connectable": bool(getattr(adv, "connectable", None)),
                "last_seen": _now_iso(),
            }
        )
    return result


async def _discover_target(
    *,
    timeout: int,
    retry: int,
    interface: str | None,
    device_name: str | None,
    mac_address: str | None,
    service_uuid: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    merged: dict[str, dict[str, Any]] = {}
    interface_used: str | None = interface

    for _ in range(retry):
        devices = await _scan_once(timeout, interface)
        for item in devices:
            if not _matches_filters(
                address=item.get("address", ""),
                name=item.get("name"),
                service_uuids=list(item.get("service_uuids") or []),
                device_name=device_name,
                mac_address=mac_address,
                service_uuid=service_uuid,
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
                    current.get("rssi") is None
                    or item.get("rssi") > current.get("rssi")
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
                return item, None, interface_used
        return (
            None,
            {
                "code": "not_found",
                "message": _(
                    "err.not_found",
                    default="No SwitchBot BLE device matched the provided mac_address.",
                    mac_address=mac_address,
                ),
            },
            interface_used,
        )

    if device_name:
        needle = device_name.casefold()
        matches = [
            item for item in items if needle in str(item.get("name") or "").casefold()
        ]
        if not matches:
            return (
                None,
                {
                    "code": "not_found",
                    "message": _(
                        "err.not_found",
                        default="No SwitchBot BLE device matched the provided device_name.",
                        device_name=device_name,
                    ),
                },
                interface_used,
            )
        if len(matches) > 1:
            return (
                None,
                {
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
                },
                interface_used,
            )
        return matches[0], None, interface_used

    return (
        None,
        {
            "code": "invalid_argument",
            "message": _(
                "err.invalid_argument",
                default="Either mac_address or device_name is required.",
            ),
        },
        interface_used,
    )


async def _read_device_status(
    *,
    device: dict[str, Any],
    timeout: int,
    limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from bleak import BleakClient

    address = str(device.get("address") or "")
    discovered_services: list[dict[str, Any]] = []
    capabilities: list[dict[str, Any]] = []
    characteristics: list[dict[str, Any]] = []
    raw_values: dict[str, str] = {}
    battery: int | None = None

    async with BleakClient(address, timeout=timeout) as client:
        services = getattr(client, "services", None)
        if services is None:
            try:
                services = await client.get_services()  # type: ignore[attr-defined]
            except Exception:
                services = None

        if services is not None:
            for service in services:
                service_item: dict[str, Any] = {
                    "uuid": getattr(service, "uuid", None),
                    "description": getattr(service, "description", None),
                    "characteristics": [],
                }
                for char in getattr(service, "characteristics", []) or []:
                    properties = list(getattr(char, "properties", []) or [])
                    char_item: dict[str, Any] = {
                        "uuid": getattr(char, "uuid", None),
                        "description": getattr(char, "description", None),
                        "properties": properties,
                    }
                    if "read" in {p.lower() for p in properties}:
                        try:
                            data = await client.read_gatt_char(getattr(char, "uuid"))
                            hex_value = data.hex()
                            char_item["value_hex"] = hex_value
                            raw_values[str(getattr(char, "uuid", ""))] = hex_value
                            if (
                                str(getattr(char, "uuid", "")).casefold()
                                == _BATTERY_UUID
                            ):
                                try:
                                    battery = int(data[0])
                                except Exception:
                                    battery = battery
                        except Exception as exc:
                            char_item["read_error"] = str(exc)
                    service_item["characteristics"].append(char_item)
                    characteristics.append(char_item)
                discovered_services.append(service_item)
                capabilities.append(
                    {
                        "uuid": getattr(service, "uuid", None),
                        "description": getattr(service, "description", None),
                        "characteristic_count": len(service_item["characteristics"]),
                    }
                )

    if limit > 0:
        characteristics = characteristics[:limit]
        discovered_services = discovered_services[:limit]

    status = {
        "connected": True,
        "battery": battery if battery is not None else device.get("battery"),
        "services": discovered_services,
        "characteristics": characteristics,
        "raw_values": raw_values,
    }
    return status, {"capabilities": capabilities}


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    device = result.get("device", {}) or {}
    status = result.get("status", {}) or {}
    lines = [
        _(
            "msg.summary",
            default="SwitchBot BLE status fetched: {device_name} ({device_id}).",
            device_name=device.get("device_name") or device.get("name") or "(unknown)",
            device_id=device.get("device_id") or device.get("address") or "(unknown)",
        ),
        f"Address: {device.get('address') or '-'}",
        f"RSSI: {device.get('rssi')}",
        f"Battery: {status.get('battery')}",
        f"Connected: {status.get('connected')}",
        f"Services: {len(status.get('services') or [])}",
        f"Characteristics: {len(status.get('characteristics') or [])}",
    ]
    for item in status.get("characteristics", [])[:10]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- {uuid} props={props} value={value}".format(
                uuid=item.get("uuid") or "(unknown)",
                props=", ".join(item.get("properties") or []) or "-",
                value=item.get("value_hex") or item.get("read_error") or "-",
            )
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("output_format") or "json").lower()
    interface = args.get("interface")
    device_name = args.get("device_name")
    mac_address = args.get("mac_address")
    service_uuid = args.get("service_uuid")

    try:
        timeout = int(args.get("timeout", 8))
        retry = int(args.get("retry", 2))
        limit = int(args.get("limit", 0))
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_numeric",
                    default="Timeout, retry, and limit must be integers.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if timeout <= 0 or retry <= 0 or limit < 0:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_range",
                    default="Timeout and retry must be greater than 0; limit must be 0 or greater.",
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
        device, err, interface_used = asyncio.run(
            _discover_target(
                timeout=timeout,
                retry=retry,
                interface=str(interface) if interface else None,
                device_name=str(device_name) if device_name else None,
                mac_address=str(mac_address) if mac_address else None,
                service_uuid=str(service_uuid) if service_uuid else None,
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

        status, extra = asyncio.run(
            _read_device_status(device=device, timeout=timeout, limit=limit)
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "ok": True,
            "device": {
                "device_id": device.get("address"),
                "device_name": device.get("name"),
                "device_type": device.get("device_type"),
                "hub_id": None,
                "online": True,
                "battery": status.get("battery"),
                "reachable": True,
                "address": device.get("address"),
                "rssi": device.get("rssi"),
                "service_uuids": device.get("service_uuids") or [],
                "manufacturer_data": device.get("manufacturer_data") or {},
                "connectable": device.get("connectable"),
                "last_seen": device.get("last_seen"),
            },
            "status": status,
            "capabilities": extra.get("capabilities", []),
            "interface_used": interface_used,
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
