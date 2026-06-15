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
STATUS_LABEL = "tool:switchbot_ble_scan"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "switchbot_ble_scan",
        "description": _(
            "tool.description",
            default=(
                "Discover nearby SwitchBot BLE devices and return a JSON or text list."
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
                    "default": 5,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default=("Scan timeout in seconds."),
                    ),
                },
                "retry": {
                    "type": "integer",
                    "default": 1,
                    "minimum": 1,
                    "description": _(
                        "param.retry.description",
                        default=("How many BLE scan rounds to run before returning."),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default=(
                            "Maximum number of devices to return. 0 means unlimited."
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


_SWITCHBOT_HINTS = {
    0x0969,
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
    if "2409" in manufacturer_data:
        return True
    return False


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
        result.append(
            {
                "name": device.name or getattr(adv, "local_name", None) or "Unknown",
                "address": device.address,
                "rssi": getattr(adv, "rssi", None),
                "device_type": (
                    "switchbot"
                    if _looks_like_switchbot(
                        device.name or getattr(adv, "local_name", None),
                        manufacturer_data,
                    )
                    else "ble"
                ),
                "service_uuids": service_uuids,
                "manufacturer_data": manufacturer_data,
                "connectable": bool(getattr(adv, "connectable", None)),
                "last_seen": _now_iso(),
            }
        )
    return result


async def _scan_rounds(
    *,
    timeout: int,
    retry: int,
    interface: str | None,
    device_name: str | None,
    mac_address: str | None,
    service_uuid: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
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
        if limit > 0 and len(merged) >= limit:
            break

    items = list(merged.values())
    items.sort(
        key=lambda x: (
            0 if x.get("device_type") == "switchbot" else 1,
            -(int(x["rssi"]) if isinstance(x.get("rssi"), int) else -9999),
            str(x.get("name") or ""),
            str(x.get("address") or ""),
        )
    )
    if limit > 0:
        items = items[:limit]
    return items, interface_used


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    items = result.get("items", [])
    lines = [
        _(
            "msg.summary",
            default="SwitchBot BLE scan completed: {count} device(s) found in {elapsed_ms} ms.",
            count=result.get("count", 0),
            elapsed_ms=result.get("elapsed_ms", 0),
        )
    ]
    interface_used = result.get("interface_used")
    if interface_used:
        lines.append(f"Interface used: {interface_used}")
    for item in items:
        service_uuids = item.get("service_uuids") or []
        lines.append(
            "- {name} [{dtype}] addr={addr} rssi={rssi} connectable={conn} services={services}".format(
                name=item.get("name") or "(unknown)",
                dtype=item.get("device_type") or "(unknown)",
                addr=item.get("address") or "(unknown)",
                rssi=item.get("rssi"),
                conn=item.get("connectable"),
                services=", ".join(service_uuids) if service_uuids else "-",
            )
        )
    if not items:
        lines.append(
            _("msg.no_devices", default="No SwitchBot BLE devices were found.")
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("output_format") or "json").lower()
    interface = args.get("interface")
    device_name = args.get("device_name")
    mac_address = args.get("mac_address")
    service_uuid = args.get("service_uuid")

    try:
        timeout = int(args.get("timeout", 5))
        retry = int(args.get("retry", 1))
        limit = int(args.get("limit", 0))
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_numeric",
                    default=("Timeout, retry, and limit must be integers."),
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
                    default=(
                        "Timeout and retry must be greater than 0; limit must be 0 or greater."
                    ),
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
        items, interface_used = asyncio.run(
            _scan_rounds(
                timeout=timeout,
                retry=retry,
                interface=str(interface) if interface else None,
                device_name=str(device_name) if device_name else None,
                mac_address=str(mac_address) if mac_address else None,
                service_uuid=str(service_uuid) if service_uuid else None,
                limit=limit,
            )
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "ok": True,
            "count": len(items),
            "items": items,
            "interface_used": interface_used,
            "elapsed_ms": elapsed_ms,
            "fetched_at": _now_iso(),
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
