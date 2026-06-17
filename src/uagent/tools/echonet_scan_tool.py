from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from typing import Any

from .echonet_cache_shared import cache_get, cache_set
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_scan"

_MULTICAST_ADDR = ("224.0.23.0", 3610)
_DEFAULT_TIMEOUT = 4
_DEFAULT_RETRY = 1
_DEFAULT_LIMIT = 50
_CACHE_TTL_SECONDS = 10
_DEFAULT_USER_EOJ = bytes.fromhex("05FF01")
_NODE_PROFILE_EOJ = bytes.fromhex("0EF001")
_EPC_NODE_PROFILE = {0xD5, 0xD6, 0xD7, 0x8A, 0x83}

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "echonet_scan",
        "description": _(
            "tool.description",
            default=(
                "Discover ECHONET Lite nodes on the local network and return a JSON or text list."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Receive wait time in seconds for ECHONET Lite discovery.",
                    ),
                },
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default=("Local interface IPv4/name (optional)."),
                    ),
                },
                "retry": {
                    "type": "integer",
                    "default": _DEFAULT_RETRY,
                    "minimum": 1,
                    "description": _(
                        "param.retry.description",
                        default="Discovery rounds.",
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_LIMIT,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of nodes to return. 0 means unlimited.",
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


_EPC_NAMES = {
    0xD5: "self_node_instance_list_s",
    0xD6: "self_node_class_list_s",
    0xD7: "self_node_instance_list",
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


def _is_ipv4_address(value: str) -> bool:
    try:
        socket.inet_aton(value)
        return value.count(".") == 3
    except Exception:
        return False


def _resolve_interface(interface: str | None) -> tuple[str | None, str | None]:
    raw = (interface or "").strip()

    def _is_virtual_name(name: str) -> bool:
        low = name.lower()
        return any(
            token in low
            for token in (
                "bluetooth",
                "loopback",
                "virtual",
                "vmware",
                "hyper-v",
                "teredo",
                "isatap",
                "tunnel",
                "tap",
                "vpn",
            )
        )

    def _score_interface(name: str, addr: str) -> int:
        low = name.lower()
        score = 0
        if _is_virtual_name(name):
            score -= 100
        if any(token in low for token in ("ethernet", "wi-fi", "wifi", "wlan")):
            score += 20
        if low.startswith(("eth", "en", "lan")):
            score += 10
        if addr.startswith("192.168."):
            score += 15
        elif addr.startswith("10."):
            score += 12
        elif addr.startswith("172."):
            try:
                second = int(addr.split(".", 2)[1])
            except Exception:
                second = -1
            if 16 <= second <= 31:
                score += 12
        elif addr.startswith("169.254."):
            score -= 20
        elif addr.startswith("127."):
            score -= 50
        return score

    def _first_ipv4_for_name(target: str) -> tuple[str | None, str | None]:
        try:
            import psutil  # type: ignore

            for name, addrs in psutil.net_if_addrs().items():
                if name.lower() != target:
                    continue
                if _is_virtual_name(name):
                    continue
                for addr in addrs:
                    if getattr(addr, "family", None) == socket.AF_INET and addr.address:
                        ip = addr.address.strip()
                        if _is_ipv4_address(ip):
                            return ip, name
        except Exception:
            pass
        return None, None

    if raw:
        if _is_ipv4_address(raw):
            return raw, raw

        ip, name = _first_ipv4_for_name(raw.lower())
        if ip:
            return ip, name

        try:
            resolved = socket.gethostbyname(raw)
            if _is_ipv4_address(resolved):
                return resolved, raw
        except Exception:
            pass

        raise ValueError(
            _(  # type: ignore[used-before-def]  # noqa: F823
                "err.invalid_interface",
                default=(
                    "Error: Could not resolve interface '{interface}' to a local IPv4 address."
                ),
                interface=raw,
            )
        )

    try:
        import psutil  # type: ignore

        candidates: list[tuple[int, str, str]] = []
        for name, addrs in psutil.net_if_addrs().items():
            if _is_virtual_name(name):
                continue
            for addr in addrs:
                if getattr(addr, "family", None) != socket.AF_INET or not addr.address:
                    continue
                ip = addr.address.strip()
                if not _is_ipv4_address(ip):
                    continue
                candidates.append((_score_interface(name, ip), name, ip))

        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1].lower()), reverse=True)
            _, best_name, best_ip = candidates[0]
            return best_ip, best_name
    except Exception:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            if _is_ipv4_address(local_ip):
                return local_ip, local_ip
    except Exception:
        pass

    return None, None


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


def _eoj_bytes(text: str | None) -> bytes | None:
    normalized = _normalize_eoj(text)
    if normalized is None:
        return None
    return bytes.fromhex(normalized)


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
    for _i in range(opc):
        if idx + 2 > len(raw):
            break
        epc = raw[idx]
        pdc = raw[idx + 1]
        idx += 2
        edt = raw[idx : idx + pdc]
        idx += pdc
        properties.append(
            {
                "epc": f"{epc:02X}",
                "name": _EPC_NAMES.get(epc, f"epc_{epc:02X}"),
                "value": _property_value(epc, edt)[0],
                "format": _property_value(epc, edt)[1],
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


def _query_frames(
    *,
    packet: bytes,
    destination: tuple[str, int],
    bind_ip: str | None,
    timeout: int,
    retry: int,
    limit: int,
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
        if bind_ip:
            try:
                sock.bind((bind_ip, 0))
            except Exception:
                sock.bind(("0.0.0.0", 0))
            try:
                sock.setsockopt(
                    socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(bind_ip)
                )
            except Exception:
                pass
        else:
            sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.25)

        frames: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for attempt in range(retry):
            try:
                sock.sendto(packet, destination)
            except Exception:
                break
            deadline = time.monotonic() + timeout
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
                parsed["source_ip"] = source[0] if source else None
                parsed["source_port"] = source[1] if source else None
                key = (
                    parsed.get("source_ip"),
                    parsed.get("seoj"),
                    parsed.get("deoj"),
                    parsed.get("esv"),
                    tuple(
                        (prop.get("epc"), prop.get("raw_hex"))
                        for prop in parsed.get("properties", [])
                    ),
                )
                if key in seen:
                    continue
                seen.add(key)
                frames.append(parsed)
                if limit > 0 and len(frames) >= limit:
                    return frames
            if limit > 0 and len(frames) >= limit:
                break
            if attempt + 1 < retry:
                time.sleep(0.15)
        return frames
    finally:
        sock.close()


def _property_map(properties: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for prop in properties:
        epc = str(prop.get("epc") or "").upper()
        if not epc:
            continue
        if epc in mapped:
            if prop.get("raw_hex") and prop.get("raw_hex") != mapped[epc].get(
                "raw_hex"
            ):
                continue
        mapped[epc] = dict(prop)
    return mapped


def _merge_properties(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        for prop in group:
            key = (str(prop.get("epc") or ""), str(prop.get("raw_hex") or ""))
            if key[0]:
                merged[key] = dict(prop)
    return list(merged.values())


def _summarize_node_item(
    source_ip: str | None, frames: list[dict[str, Any]]
) -> dict[str, Any]:
    properties = _merge_properties(*(frame.get("properties") or [] for frame in frames))
    node_profile_props = _property_map(properties)
    eoj_list: list[str] = []
    for epc in ("D5", "D6", "D7"):
        prop = node_profile_props.get(epc)
        if prop and isinstance(prop.get("value"), list):
            eoj_list.extend([str(v).upper() for v in prop.get("value") if v])
    eoj_list = sorted({v for v in eoj_list if v})

    manufacturer = None
    if node_profile_props.get("8A"):
        manufacturer = node_profile_props["8A"].get("raw_hex") or node_profile_props[
            "8A"
        ].get("value")
    model = None
    for candidate in ("83", "8B", "8C"):
        if node_profile_props.get(candidate):
            model = node_profile_props[candidate].get("raw_hex") or node_profile_props[
                candidate
            ].get("value")
            break

    node_profile = {
        "eoj": frames[0].get("seoj") if frames else "0EF001",
        "properties": properties,
    }

    return {
        "ip": source_ip,
        "node_id": source_ip,
        "node_profile": node_profile,
        "manufacturer": manufacturer,
        "model": model,
        "eoj_list": eoj_list,
        "reachable": bool(frames),
        "last_seen": _now_iso(),
    }


def _format_text(payload: dict[str, Any]) -> str:
    lines = [
        _(
            "msg.summary",
            default="ECHONET Lite discovery completed: {count} node(s) found in {elapsed_ms} ms.",
            count=payload.get("count", 0),
            elapsed_ms=payload.get("elapsed_ms", 0),
        )
    ]
    if payload.get("interface_used"):
        lines.append(f"Interface: {payload.get('interface_used')}")
    if payload.get("bind_ip"):
        lines.append(f"Bind IP: {payload.get('bind_ip')}")
    lines.append(f"Retry: {payload.get('retry')}")
    lines.append(f"Timeout: {payload.get('timeout')} s")
    lines.append("")

    items = payload.get("items") or []
    if not items:
        lines.append(_("msg.no_devices", default="No ECHONET Lite nodes were found."))
        return "\n".join(lines).strip()

    for idx, item in enumerate(items, 1):
        lines.append(f"[{idx}] {item.get('ip_address') or '(unknown)'}")
        if item.get("node_id"):
            lines.append(f"  node_id: {item.get('node_id')}")
        if item.get("manufacturer"):
            lines.append(f"  manufacturer: {item.get('manufacturer')}")
        if item.get("model"):
            lines.append(f"  model: {item.get('model')}")
        if item.get("eoj_list"):
            lines.append(f"  eoj_list: {', '.join(item.get('eoj_list') or [])}")
        lines.append(f"  reachable: {item.get('reachable')}")
        if item.get("last_seen"):
            lines.append(f"  last_seen: {item.get('last_seen')}")
        node_profile = item.get("node_profile") or {}
        props = node_profile.get("properties") or []
        lines.append(f"  node_profile_properties: {len(props)}")
        lines.append("")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    timeout = _normalize_int(args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1)
    retry = _normalize_int(args.get("retry", _DEFAULT_RETRY), _DEFAULT_RETRY, 1)
    limit = _normalize_int(args.get("limit", _DEFAULT_LIMIT), _DEFAULT_LIMIT, 0)
    output_format = str(args.get("fmt") or "json").strip().lower()
    interface_arg = args.get("interface")
    interface = str(interface_arg).strip() if interface_arg is not None else ""

    if timeout < 1:
        timeout = _DEFAULT_TIMEOUT
    if retry < 1:
        retry = _DEFAULT_RETRY
    if limit < 0:
        limit = _DEFAULT_LIMIT

    start_time = time.monotonic()
    cache_key = {
        "timeout": timeout,
        "interface": interface,
        "retry": retry,
        "limit": limit,
    }
    cached = cache_get("scan", cache_key, ttl_seconds=_CACHE_TTL_SECONDS)
    if cached is not None:
        payload = dict(cached.get("value") or {})
        payload["cache"] = {
            "hit": True,
            "age_ms": cached.get("age_ms"),
            "namespace": cached.get("namespace"),
            "key": cached.get("key"),
        }
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    try:
        bind_ip, interface_used = _resolve_interface(interface)
        packet = _build_get_request(_NODE_PROFILE_EOJ, sorted(_EPC_NODE_PROFILE))
        frames = _query_frames(
            packet=packet,
            destination=_MULTICAST_ADDR,
            bind_ip=bind_ip,
            timeout=timeout,
            retry=retry,
            limit=limit,
        )

        grouped: dict[str, list[dict[str, Any]]] = {}
        for frame in frames:
            source_ip = str(frame.get("source_ip") or frame.get("source_port") or "")
            if not source_ip:
                continue
            grouped.setdefault(source_ip, []).append(frame)

        items = [
            _summarize_node_item(source_ip, grouped[source_ip])
            for source_ip in sorted(grouped.keys())
        ]
        if limit > 0:
            items = items[:limit]

        payload = {
            "ok": True,
            "count": len(items),
            "items": items,
            "interface_used": interface_used,
            "bind_ip": bind_ip,
            "timeout": timeout,
            "retry": retry,
            "limit": limit,
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
            "cache": {
                "hit": False,
                "namespace": "scan",
                "key": json.dumps(cache_key, ensure_ascii=False, sort_keys=True),
            },
        }
        cache_set("scan", cache_key, payload)
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
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
