from __future__ import annotations

import json
import socket
import time
import random
import struct
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_control"

_DEFAULT_TIMEOUT = 4
_DEFAULT_USER_EOJ = bytes.fromhex("05FF01")
_NODE_PROFILE_EOJ = bytes.fromhex("0EF001")

_EPC_NAMES = {
    0x80: "operation_status",
    0x81: "installation_location",
    0x82: "standard_version_information",
    0x83: "identification_number",
    0x8A: "manufacturer_code",
    0x8B: "product_code",
    0x8C: "property_map",
    0x9D: "set_property_map",
    0x9E: "get_property_map",
    0x9F: "inf_property_map",
    0xD5: "self_node_instance_list_s",
    0xD6: "self_node_class_list_s",
    0xD7: "self_node_instance_list",
}

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "echonet_control",
        "description": _(
            "tool.description",
            default=(
                "Execute basic ECHONET Lite control on a node and return a JSON or text result."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "echonet control",
                "echonet_control",
                "echonet",
                "ECHONET",
                "execute",
                "basic",
            ],
        ),
        "x_search_terms_en": [
            "echonet control",
            "echonet_control",
            "echonet",
            "ECHONET",
            "execute",
            "basic",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Target node IPv4 address.",
                    ),
                },
                "eoj": {
                    "type": "string",
                    "description": _(
                        "param.eoj.description",
                        default=("Target EOJ (default: node profile)."),
                    ),
                },
                "obj": {
                    "type": "string",
                    "description": _(
                        "param.obj.description",
                        default=("Object code filter (e.g. '0130')."),
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "on",
                        "off",
                        "open",
                        "close",
                        "set_value",
                        "lock",
                        "unlock",
                    ],
                    "description": _(
                        "param.action.description",
                        default="Action: on/off/open/close/set_value/lock/unlock.",
                    ),
                },
                "value": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": _(
                        "param.value.description",
                        default="Optional numeric value for set_value/open/close actions. Range: 0 to 100.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout (seconds).",
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
            "required": ["ip_address", "action"],
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
        result = default
    if result < minimum:
        result = default if default >= minimum else minimum
    return result


def _is_ipv4_address(value: str) -> bool:
    try:
        socket.inet_aton(value)
        return value.count(".") == 3
    except Exception:
        return False


def _normalize_eoj(text: str | None) -> str | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    raw = raw.replace("0x", "").replace("0X", "")
    for sep in (" ", ":", "-", "."):
        raw = raw.replace(sep, "")
    raw = raw.upper()
    if len(raw) != 6:
        return None
    try:
        bytes.fromhex(raw)
    except Exception:
        return None
    return raw


def _normalize_object_code(text: str | None) -> str | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    raw = raw.replace("0x", "").replace("0X", "")
    for sep in (" ", ":", "-", "."):
        raw = raw.replace(sep, "")
    raw = raw.upper()
    if len(raw) != 4:
        return None
    try:
        bytes.fromhex(raw)
    except Exception:
        return None
    return raw


def _normalize_epc(text: str | None) -> str | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    raw = raw.replace("0x", "").replace("0X", "")
    for sep in (" ", ":", "-", "."):
        raw = raw.replace(sep, "")
    raw = raw.upper()
    if len(raw) != 2:
        return None
    try:
        bytes.fromhex(raw)
    except Exception:
        return None
    return raw


def _eoj_bytes(text: str | None) -> bytes | None:
    normalized = _normalize_eoj(text)
    if normalized is None:
        return None
    return bytes.fromhex(normalized)


def _decode_eoj_list(data: bytes) -> list[str]:
    if not data:
        return []
    items: list[str] = []
    for start in range(0, len(data) - (len(data) % 3), 3):
        chunk = data[start : start + 3]
        if len(chunk) == 3:
            items.append(chunk.hex().upper())
    return items


def _property_value(epc: int, edt: bytes) -> tuple[Any, str]:
    if epc in {0xD5, 0xD6, 0xD7}:
        return _decode_eoj_list(edt), "eoj_list"
    if not edt:
        return None, "empty"
    if len(edt) == 1:
        return edt[0], "uint8"
    if len(edt) == 2:
        return int.from_bytes(edt, "big"), "uint16"
    if len(edt) == 3:
        return int.from_bytes(edt, "big"), "uint24"
    if len(edt) == 4:
        return int.from_bytes(edt, "big"), "uint32"
    return edt.hex().upper(), "hex"


def _build_set_request(
    target_eoj: bytes, epc: int, edt: bytes, tid: int | None = None
) -> bytes:
    tid_bytes = (
        struct.pack(">H", tid & 0xFFFF)
        if tid is not None
        else struct.pack(">H", random.randint(1, 0xFFFF))
    )
    return b"".join(
        [
            b"\x10\x81",
            tid_bytes,
            _DEFAULT_USER_EOJ,
            target_eoj,
            b"\x61",
            b"\x01",
            bytes([epc & 0xFF, len(edt)]),
            edt,
        ]
    )


def _parse_frame(raw: bytes) -> dict[str, Any] | None:
    if len(raw) < 12:
        return None
    if raw[0] != 0x10 or raw[1] != 0x81:
        return None

    seoj = raw[4:7].hex().upper()
    deoj = raw[7:10].hex().upper()
    esv = raw[10]
    opc = raw[11]
    idx = 12
    properties: list[dict[str, Any]] = []
    for _ in range(opc):
        if idx + 2 > len(raw):
            break
        epc = raw[idx]
        pdc = raw[idx + 1]
        idx += 2
        edt = raw[idx : idx + pdc]
        idx += pdc
        value, fmt = _property_value(epc, edt)
        properties.append(
            {
                "epc": f"{epc:02X}",
                "name": _EPC_NAMES.get(epc, f"epc_{epc:02X}"),
                "value": value,
                "format": fmt,
                "access": "read",
                "raw_hex": edt.hex().upper(),
            }
        )

    return {
        "seoj": seoj,
        "deoj": deoj,
        "esv": f"{esv:02X}",
        "opc": opc,
        "properties": properties,
        "raw_hex": raw.hex().upper(),
    }


def _property_map(properties: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for prop in properties:
        epc = str(prop.get("epc") or "").upper()
        if epc:
            mapped[epc] = dict(prop)
    return mapped


def _class_name_from_eoj(eoj: str | None) -> str | None:
    normalized = _normalize_eoj(eoj)
    if not normalized:
        return None
    return f"EOJ_{normalized}"


def _object_code_to_eoj(object_code: str | None) -> str | None:
    normalized = _normalize_object_code(object_code)
    if not normalized:
        return None
    return f"{normalized}01"


def _resolve_target_eoj(
    eoj: str | None, object_code: str | None
) -> tuple[str, bytes, str | None]:
    if eoj:
        normalized = _normalize_eoj(eoj)
        if normalized is None:
            raise ValueError(
                _(
                    "err.invalid_eoj",
                    default="Error: Could not parse EOJ '{eoj}'.",
                    eoj=eoj,
                )
            )
        return normalized, bytes.fromhex(normalized), _class_name_from_eoj(normalized)

    if object_code:
        object_eoj = _object_code_to_eoj(object_code)
        if object_eoj is None:
            raise ValueError(
                _(
                    "err.invalid_object_code",
                    default="Error: Could not parse object_code '{object_code}'.",
                    object_code=object_code,
                )
            )
        return object_eoj, bytes.fromhex(object_eoj), _class_name_from_eoj(object_eoj)

    return "0EF001", _NODE_PROFILE_EOJ, "node_profile"


def _resolve_device_kind(
    target_eoj_text: str,
) -> tuple[str, set[str] | None]:
    eoj_upper = target_eoj_text.upper()
    class_code = eoj_upper[2:4]
    DEVICE_KINDS: dict[str, tuple[str, set[str]]] = {
        "30": ("aircon", {"on", "off", "set_value"}),
        "33": ("ventfan", {"on", "off"}),
        "34": ("ventfan_ac", {"on", "off"}),
        "35": ("aircleaner", {"on", "off"}),
        "90": ("lighting", {"on", "off"}),
        "91": ("lighting", {"on", "off"}),
        "92": ("lighting", {"on", "off"}),
        "A0": ("buzzer", {"on", "off"}),
        "A1": ("ev_charger", {"on", "off", "set_value"}),
        "6E": ("toilet", {"lock", "unlock"}),
        "6F": ("lock", {"lock", "unlock"}),
    }
    entry = DEVICE_KINDS.get(class_code)
    if entry is None:
        return "unknown", None
    return entry


def _build_control_payload(
    action: str, value: int | None
) -> tuple[int, bytes, int | None, dict[str, Any] | None]:
    normalized = action.casefold().strip()
    if normalized == "on":
        return 0x80, bytes([0x30]), 1, None
    if normalized == "off":
        return 0x80, bytes([0x31]), 0, None
    if normalized == "open":
        if value is not None and (value < 0 or value > 100):
            return (
                0,
                b"",
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.invalid_value_range",
                        default="The value field must be between 0 and 100.",
                    ),
                },
            )
        return 0xE0, bytes([0x41]), 100, None
    if normalized == "close":
        if value is not None and (value < 0 or value > 100):
            return (
                0,
                b"",
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.invalid_value_range",
                        default="The value field must be between 0 and 100.",
                    ),
                },
            )
        return 0xE0, bytes([0x42]), 0, None
    if normalized == "lock":
        if value is not None and (value < 0 or value > 100):
            return (
                0,
                b"",
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.invalid_value_range",
                        default="The value field must be between 0 and 100.",
                    ),
                },
            )
        return 0xE0, bytes([0x31]), 1, None
    if normalized == "unlock":
        if value is not None and (value < 0 or value > 100):
            return (
                0,
                b"",
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.invalid_value_range",
                        default="The value field must be between 0 and 100.",
                    ),
                },
            )
        return 0xE0, bytes([0x30]), 2, None
    if normalized == "set_value":
        if value is None:
            return (
                0,
                b"",
                None,
                {
                    "code": "missing_argument",
                    "message": _(
                        "err.missing_value_for_set_value",
                        default="Error: value field is required for set_value action.",
                    ),
                },
            )
        if value < 0 or value > 100:
            return (
                0,
                b"",
                None,
                {
                    "code": "invalid_argument",
                    "message": _(
                        "err.invalid_value_range",
                        default="The value field must be between 0 and 100.",
                    ),
                },
            )
        return 0xB3, bytes([value]), value, None
    return (
        0,
        b"",
        None,
        {
            "code": "unsupported_action",
            "message": _(
                "err.unsupported_action",
                default="Error: Unsupported action '{action}'.",
                action=action,
            ),
        },
    )


def _send_control(
    *,
    ip_address: str,
    target_eoj: bytes,
    epc: int,
    edt: bytes,
    timeout: int,
) -> list[dict[str, Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            sock.bind(("0.0.0.0", 3610))
        except OSError:
            sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.25)

        deadline = time.monotonic() + timeout
        retry_interval = 0.8
        next_retry = 0.0
        frames: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        transmitted = False

        while time.monotonic() < deadline:
            now = time.monotonic()
            if not transmitted:
                packet = _build_set_request(target_eoj, epc, edt)
                sock.sendto(packet, (ip_address, 3610))
                transmitted = True
                next_retry = now + retry_interval
            elif now >= next_retry and not frames:
                packet = _build_set_request(target_eoj, epc, edt)
                sock.sendto(packet, (ip_address, 3610))
                next_retry = now + retry_interval

            try:
                data, source = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            parsed = _parse_frame(data)
            if not parsed:
                continue
            source_ip = source[0] if source else ip_address
            key = (source_ip, parsed.get("seoj") or "", parsed.get("deoj") or "")
            if key in seen:
                continue
            seen.add(key)
            parsed["source_ip"] = source_ip
            frames.append(parsed)
        return frames
    finally:
        sock.close()


def _build_result(
    *,
    ip_address: str,
    target_eoj: str,
    frames: list[dict[str, Any]],
    epc: int,
    edt: bytes,
    action: str,
    value: int | None,
) -> dict[str, Any]:
    properties: list[dict[str, Any]] = []
    frames_by_object: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        key = str(frame.get("seoj") or target_eoj)
        frames_by_object.setdefault(key, []).append(frame)

    for eoj, group in frames_by_object.items():
        merged_props: list[dict[str, Any]] = []
        for frame in group:
            merged_props.extend(frame.get("properties") or [])
        properties.extend(merged_props)

    value_ref, fmt = _property_value(epc, edt)

    return {
        "node": {
            "ip": ip_address,
            "node_id": ip_address,
            "available": bool(frames),
            "reachable": bool(frames),
            "last_updated": _now_iso(),
        },
        "properties": properties[:10],
        "control": {
            "action": action,
            "epc": f"{epc:02X}",
            "edt_hex": edt.hex().upper(),
            "value": value,
            "success": bool(frames),
        },
    }


def _format_text(payload: dict[str, Any]) -> str:
    control = payload.get("control") or {}
    lines = [
        _(
            "msg.summary",
            default="ECHONET Lite control completed: {action} on {ip_address} in {elapsed_ms} ms.",
            action=control.get("action") or "(unknown)",
            ip_address=payload.get("node", {}).get("ip") or "(unknown)",
            elapsed_ms=payload.get("elapsed_ms", 0),
        )
    ]
    node = payload.get("node") or {}
    lines.append(f"IP: {node.get('ip_address') or '-'}")
    if node.get("node_id"):
        lines.append(f"Node ID: {node.get('node_id')}")
    lines.append(f"Available: {node.get('available')}")
    lines.append(f"Reachable: {node.get('reachable')}")
    lines.append(f"Properties: {len(payload.get('properties') or [])}")
    for prop in (payload.get("properties") or [])[:5]:
        lines.append(
            "- {epc} {name} = {value}".format(
                epc=prop.get("epc") or "-",
                name=prop.get("name") or "-",
                value=prop.get("value"),
            )
        )
    lines.append(f"Action: {control.get('action')}")
    lines.append(f"EPC: {control.get('epc')}")
    lines.append(f"Value: {control.get('value')}")
    lines.append(f"Payload: {control.get('edt_hex')}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_address = str(args.get("ip") or "").strip()
    eoj = args.get("eoj")
    object_code = args.get("obj")
    action = str(args.get("action") or "").strip()
    raw_value = args.get("value")
    output_format = str(args.get("fmt") or "json").strip().lower()

    try:
        timeout = _normalize_int(
            args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1
        )
    except Exception:
        timeout = _DEFAULT_TIMEOUT

    if not ip_address or not _is_ipv4_address(ip_address):
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_ip_address",
                    default="Error: ip_address must be a valid IPv4 address.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if not action:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.missing_action",
                    default="Error: action is required.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    try:
        target_eoj_text, target_eoj_bytes, class_name = _resolve_target_eoj(
            str(eoj) if eoj is not None else None,
            str(object_code) if object_code is not None else None,
        )
    except ValueError as exc:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": str(exc),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    kind_label, supported_actions = _resolve_device_kind(target_eoj_text)
    if supported_actions is not None and action.casefold() not in supported_actions:
        payload = {
            "ok": False,
            "error": {
                "code": "unsupported_action_for_device",
                "message": _(
                    "err.unsupported_action_for_device",
                    default="Error: action '{action}' is not supported for {kind} yet.",
                    action=action,
                    kind=kind_label,
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    value_arg: int | None = None
    if raw_value is not None:
        try:
            value_arg = int(raw_value)
        except (ValueError, TypeError):
            pass

    epc, edt, value_ref, err = _build_control_payload(action, value_arg)
    if err:
        payload = {"ok": False, "error": err}
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    start = time.monotonic()
    try:
        frames = _send_control(
            ip_address=ip_address,
            target_eoj=target_eoj_bytes,
            epc=epc,
            edt=edt,
            timeout=timeout,
        )
        payload = _build_result(
            ip_address=ip_address,
            target_eoj=target_eoj_text,
            frames=frames,
            epc=epc,
            edt=edt,
            action=action,
            value=value_ref,
        )
        payload.update(
            {
                "ok": True,
                "elapsed_ms": int((time.monotonic() - start) * 1000),
                "target": {
                    "eoj": target_eoj_text,
                    "class_name": class_name,
                    "obj": _normalize_object_code(object_code),
                    "action": action,
                },
            }
        )
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": {
                "code": "communication_failed",
                "message": str(exc),
            },
            "elapsed_ms": int((time.monotonic() - start) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
