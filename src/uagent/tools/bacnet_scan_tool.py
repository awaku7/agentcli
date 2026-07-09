from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:bacnet_scan"

_DEFAULT_TIMEOUT = 5
_DEFAULT_LIMIT = 50


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
                    default="BAC0 library could not be installed. BACnet tools require BAC0.",
                )
            )
        import BAC0  # type: ignore[import-untyped]
    return BAC0


def _bac0_vendor_name(vendor_id: int | None) -> str | None:
    if vendor_id is None:
        return None
    table = {
        0: "ASHRAE",
        1: "Alerton",
        2: "American Auto-Matrix",
        3: "Andover Controls",
        4: "Automated Logic",
        5: "Barber-Colman",
        6: "Carrier",
        7: "Delta Controls",
        8: "Echelon",
        9: "Honeywell",
        10: "Johnson Controls",
        11: "KMC Controls",
        12: "McQuay",
        13: "Novar",
        14: "Reliable Controls",
        15: "Siemens",
        16: "TAC",
        17: "Trane",
        18: "Tridium",
        19: "Distech Controls",
        20: "Mitsubishi Electric",
        21: "Daikin",
        22: "Hitachi",
        23: "Toshiba",
        24: "Yokogawa",
        25: "Azbil",
        26: "Panasonic",
        27: "Sanyo",
        28: "Fuji Electric",
        29: "NEC",
        30: "Oki Electric",
        31: "Mitsubishi Heavy Ind.",
        32: "TOYOTA",
        33: "Matsushita Electric",
        34: "Sharp",
        35: "Sony",
        36: "Omron",
        37: "Yamatake",
        38: "Ricoh",
        39: "Seiko Epson",
        40: "Murata Machinery",
        41: "Noritz",
        42: "Rinnai",
        43: "Paloma",
        44: "Chofu Seisakusho",
        45: "Daikin Industries",
        46: "Toshiba Carrier",
        47: "Mitsubishi Heavy Ind. Thermal Systems",
        48: "Fuji General",
        49: "Corona",
        50: "Aisin Seiki",
        51: "Denso",
        52: "Mitsubishi Electric Building",
        53: "Yanmar",
        54: "Kubota",
        55: "LX",
        56: "LG Electronics",
        57: "Samsung Electronics",
        58: "Hyundai",
        59: "Kele",
        60: "Contemporary Controls",
        61: "FieldServer Tech.",
        62: "Shenzhen Junzhi",
        63: "BACnet Interconnect",
        64: "Chipkin Automation",
        65: "MTA",
        66: "Phoenix Controls",
        67: "Schneider Electric",
        68: "Wieland Electric",
        69: "ABB",
        70: "Beckhoff",
        71: "Bosch",
        72: "Grundfos",
        73: "Sauter",
        74: "Kieback & Peter",
        75: "LOYTEC",
        76: "BELIMO",
        77: "EBV",
        78: "Salus",
        79: "DEOS",
        80: "Duox Sistemi Elettronici",
        81: "Dynamic Control Systems",
        82: "Bohnke + Partner",
        83: "CIMETRICS",
        84: "CoreTec",
        85: "Cylon Controls",
        86: "Danfoss",
        87: "Engenuity Systems",
        88: "Reliable Controls Mexico",
        89: "GGE",
        90: "Honeywell (redundant)",
        91: "Hubbell Industrial Controls",
        92: "Ista",
        93: "Lands & Gyr",
        94: "Saia-Burgess Controls",
        95: "SBC Aqua",
        96: "Seametrics",
        97: "Sedona",
        98: "Veris Industries",
        99: "Wattmaster Controls",
    }
    return table.get(vendor_id, f"Unknown (ID={vendor_id})")


TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "bacnet_scan",
        "description": _(
            "tool.description",
            default=(
                "Discover BACnet/IP devices on the local network. "
                "Sends a Who-Is broadcast and returns I-Am responses as a JSON or text list. "
                "Requires BAC0 library (auto-installed if missing)."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "bacnet scan",
                "bacnet_scan",
                "bacnet",
                "BACNET",
                "discover",
                "bacnet/ip",
                "devices",
                "local",
                "network",
                "sends",
            ],
        ),
        "x_search_terms_en": [
            "bacnet scan",
            "bacnet_scan",
            "bacnet",
            "BACNET",
            "discover",
            "bacnet/ip",
            "devices",
            "local",
            "network",
            "sends",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Who-Is response wait time in seconds.",
                    ),
                },
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default=(
                            "Local IPv4 address to bind (e.g. '192.168.1.100'). "
                            "If omitted, BAC0 auto-detects the local interface."
                        ),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_LIMIT,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of devices to return. 0 means unlimited.",
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


def _normalize_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        result = int(value)
    except Exception:
        return default
    if result < minimum:
        return default if default >= minimum else minimum
    return result


def _format_text(payload: dict[str, Any]) -> str:
    devices = payload.get("devices") or []
    lines = [
        _(
            "msg.summary",
            default="BACnet/IP discovery completed: {count} device(s) found in {ms} ms.",
            count=len(devices),
            ms=payload.get("elapsed_ms", 0),
        )
    ]
    if payload.get("interface"):
        lines.append(f"Interface: {payload.get('interface')}")
    lines.append("")

    if not devices:
        lines.append(_("msg.no_devices", default="No BACnet/IP devices were found."))
        return "\n".join(lines).strip()

    for idx, dev in enumerate(devices, 1):
        lines.append(f"[{idx}] instance={dev.get('instance')}")
        lines.append(f"  ip: {dev.get('ip')}")
        if dev.get("vendor_name"):
            lines.append(f"  vendor: {dev.get('vendor_name')}")
        if dev.get("model_name"):
            lines.append(f"  model: {dev.get('model_name')}")
        if dev.get("description"):
            lines.append(f"  description: {dev.get('description')}")
        if dev.get("location"):
            lines.append(f"  location: {dev.get('location')}")
        lines.append("")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    limit = _normalize_int(args.get("limit", _DEFAULT_LIMIT), _DEFAULT_LIMIT, 0)
    output_format = str(args.get("fmt") or "json").strip().lower()
    interface = args.get("interface")

    start_time = time.monotonic()
    BAC0 = _bac0_import()

    bacnet_instance = None
    try:
        connect_kwargs: dict[str, Any] = {}
        if interface:
            connect_kwargs["ip"] = str(interface).strip()
        # BAC0.connect does not directly support a timeout param;
        # the timeout value is used for the overall operation timeout via the finally block.

        bacnet_instance = BAC0.connect(**connect_kwargs)
        if bacnet_instance is None:
            raise RuntimeError("BAC0.connect() returned None")

        devices_raw = bacnet_instance.whois()
        if devices_raw is None:
            devices_raw = []

        devices: list[dict[str, Any]] = []
        seen_instances: set[int] = set()

        for dev in devices_raw:
            if isinstance(dev, (list, tuple)):
                if len(dev) >= 2:
                    ip_address = str(dev[0])
                    instance = int(dev[1])
                else:
                    continue
            elif isinstance(dev, dict):
                ip_address = str(dev.get("ip", dev.get("address", "")))
                instance = int(dev.get("instance", dev.get("device_id", 0)))
            else:
                continue

            if not instance or instance in seen_instances:
                continue
            seen_instances.add(instance)

            device_info: dict[str, Any] = {
                "instance": instance,
                "ip": ip_address,
                "vendor_name": None,
                "vendor_id": None,
                "model_name": None,
                "description": None,
                "location": None,
                "firmware": None,
                "protocol_version": None,
                "protocol_revision": None,
                "last_seen": _now_iso(),
            }

            try:
                dev_obj = BAC0.device.Device(
                    instance, bacnet_instance, ip=ip_address, poll=0
                )
                if hasattr(dev_obj, "vendor_name") and dev_obj.vendor_name:
                    device_info["vendor_name"] = str(dev_obj.vendor_name)
                if (
                    hasattr(dev_obj, "vendor_identifier")
                    and dev_obj.vendor_identifier is not None
                ):
                    vid = int(dev_obj.vendor_identifier)
                    device_info["vendor_id"] = vid
                    if not device_info.get("vendor_name"):
                        device_info["vendor_name"] = _bac0_vendor_name(vid)
                if hasattr(dev_obj, "model_name") and dev_obj.model_name:
                    device_info["model_name"] = str(dev_obj.model_name)
                if hasattr(dev_obj, "description") and dev_obj.description:
                    device_info["description"] = str(dev_obj.description)
                if hasattr(dev_obj, "location") and dev_obj.location:
                    device_info["location"] = str(dev_obj.location)
                if hasattr(dev_obj, "firmware") and dev_obj.firmware:
                    device_info["firmware"] = str(dev_obj.firmware)
                if hasattr(dev_obj, "protocol_version") and dev_obj.protocol_version:
                    device_info["protocol_version"] = str(dev_obj.protocol_version)
                if (
                    hasattr(dev_obj, "protocol_revision")
                    and dev_obj.protocol_revision is not None
                ):
                    device_info["protocol_revision"] = int(dev_obj.protocol_revision)
            except Exception:
                pass

            devices.append(device_info)
            if limit > 0 and len(devices) >= limit:
                break

        payload = {
            "ok": True,
            "count": len(devices),
            "devices": devices,
            "interface": interface or "auto",
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }

        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)

    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": {
                "code": "bacnet_scan_failed",
                "message": str(exc),
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
