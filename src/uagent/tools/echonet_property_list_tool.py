from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_property_list"

_DEFAULT_TIMEOUT = 4
_DEFAULT_LIMIT = 50
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
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "echonet_property_list",
        "description": _(
            "tool.description",
            default=(
                "Discover ECHONET Lite properties on a node and return a JSON or text list."
            ),
        ),
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
                        default=(
                            "Target EOJ (default: node profile)."
                        ),
                    ),
                },
                "obj": {
                    "type": "string",
                    "description": _(
                        "param.obj.description",
                        default=(
                            "Object code filter (e.g. '0130')."
                        ),
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
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_LIMIT,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of properties to return. 0 means unlimited.",
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
            "required": ["ip_address"],
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


def _eoj_bytes(text: str | None) -> bytes | None:
    normalized = _normalize_eoj(text)
    if normalized is None:
        return None
    return bytes.fromhex(normalized)


def _object_code_to_eoj(object_code: str | None) -> str | None:
    normalized = _normalize_object_code(object_code)
    if not normalized:
        return None
    return f"{normalized}01"


def _class_name_from_eoj(eoj: str | None) -> str | None:
    normalized = _normalize_eoj(eoj)
    if not normalized:
        return None
    return f"EOJ_{normalized}"


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


def _build_get_request(target_eoj: bytes, epcs: list[int]) -> bytes:
    props: list[bytes] = []
    for epc in epcs:
        props.append(bytes([epc & 0xFF, 0x00]))
    return b"".join(
        [
            b"\x10\x81",
            _DEFAULT_USER_EOJ,
            target_eoj,
            b"\x62",
            bytes([len(props)]),
            *props,
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


def _merge_properties(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for prop in group:
            key = (str(prop.get("epc") or ""), str(prop.get("raw_hex") or ""))
            if key[0]:
                merged[key] = dict(prop)
    return list(merged.values())


def _property_map(properties: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for prop in properties:
        epc = str(prop.get("epc") or "").upper()
        if epc:
            mapped[epc] = dict(prop)
    return mapped


def _query_node(
    *,
    ip_address: str,
    target_eoj: bytes,
    timeout: int,
) -> list[dict[str, Any]]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        except Exception:
            pass
        sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.25)

        if target_eoj.hex().upper() == "0EF001":
            request_epcs = [
                0xD5,
                0xD6,
                0xD7,
                0x80,
                0x81,
                0x82,
                0x83,
                0x8A,
                0x8C,
                0x9D,
                0x9E,
                0x9F,
            ]
        else:
            request_epcs = [0x80, 0x81, 0x82, 0x83, 0x8A, 0x8B, 0x8C, 0x9D, 0x9E, 0x9F]
        packet = _build_get_request(target_eoj, request_epcs)
        sock.sendto(packet, (ip_address, 3610))

        deadline = time.monotonic() + timeout
        frames: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        while time.monotonic() < deadline:
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


def _build_payload(
    *,
    ip_address: str,
    target_eoj: str,
    frames: list[dict[str, Any]],
) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    properties_all: list[dict[str, Any]] = []

    frames_by_object: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        key = str(frame.get("seoj") or target_eoj)
        frames_by_object.setdefault(key, []).append(frame)

    for eoj, group in frames_by_object.items():
        props = _merge_properties(*(frame.get("properties") or [] for frame in group))
        properties_all.extend(props)
        mapped = _property_map(props)
        supported_esv: list[str] = []
        if mapped:
            supported_esv = ["62", "72"]
        objects.append(
            {
                "eoj": eoj,
                "class_name": _class_name_from_eoj(eoj),
                "instance": int(eoj[-2:], 16) if len(eoj) == 6 else None,
                "properties": props,
                "supported_esv": supported_esv,
            }
        )

    node_profile_props = (
        _property_map(properties_all) if target_eoj.upper() == "0EF001" else {}
    )
    node = {
        "ip": ip_address,
        "node_id": ip_address,
        "node_profile": {
            "eoj": target_eoj,
            "properties": properties_all if target_eoj.upper() == "0EF001" else [],
        },
        "manufacturer": (
            node_profile_props.get("8A", {}).get("raw_hex")
            if node_profile_props
            else None
        ),
        "model": (
            node_profile_props.get("8B", {}).get("raw_hex")
            if node_profile_props
            else None
        ),
        "available": bool(frames),
        "reachable": bool(frames),
        "last_updated": _now_iso(),
    }

    return {
        "node": node,
        "objects": objects,
        "properties": _merge_properties(
            *[obj.get("properties") or [] for obj in objects]
        ),
        "status": {
            "target_eoj": target_eoj,
            "reachable": bool(frames),
            "response_count": len(frames),
            "last_updated": _now_iso(),
        },
    }


def _format_text(payload: dict[str, Any]) -> str:
    lines = [
        _(
            "msg.summary",
            default=(
                "ECHONET Lite property list fetched: {count} property(ies) in {elapsed_ms} ms."
            ),
            count=len(payload.get("properties") or []),
            elapsed_ms=payload.get("elapsed_ms", 0),
        )
    ]
    node = payload.get("node") or {}
    lines.append(f"IP: {node.get('ip_address') or '-'}")
    if node.get("node_id"):
        lines.append(f"Node ID: {node.get('node_id')}")
    lines.append(f"Available: {node.get('available')}")
    lines.append(f"Reachable: {node.get('reachable')}")
    lines.append(f"Objects: {len(payload.get('objects') or [])}")
    for obj in (payload.get("objects") or [])[:10]:
        lines.append(
            f"- {obj.get('eoj') or '(unknown)'} {obj.get('class_name') or ''}".rstrip()
        )
        props = obj.get("properties") or []
        for prop in props[:20]:
            lines.append(
                "  * {epc} {name} = {value}".format(
                    epc=prop.get("epc") or "-",
                    name=prop.get("name") or "-",
                    value=prop.get("value"),
                )
            )
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_address = str(args.get("ip") or "").strip()
    eoj = args.get("eoj")
    object_code = args.get("obj")
    output_format = str(args.get("fmt") or "json").strip().lower()

    try:
        timeout = _normalize_int(
            args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1
        )
        limit = _normalize_int(args.get("limit", _DEFAULT_LIMIT), _DEFAULT_LIMIT, 0)
    except Exception:
        timeout = _DEFAULT_TIMEOUT
        limit = _DEFAULT_LIMIT

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

    start = time.monotonic()
    try:
        frames = _query_node(
            ip_address=ip_address,
            target_eoj=target_eoj_bytes,
            timeout=timeout,
        )
        payload = _build_payload(
            ip_address=ip_address,
            target_eoj=target_eoj_text,
            frames=frames,
        )
        if limit > 0:
            payload["objects"] = payload.get("objects", [])[:limit]
            payload["properties"] = payload.get("properties", [])[:limit]
        payload.update(
            {
                "ok": True,
                "elapsed_ms": int((time.monotonic() - start) * 1000),
                "target": {
                    "eoj": target_eoj_text,
                    "class_name": class_name,
                    "obj": _normalize_object_code(object_code),
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
