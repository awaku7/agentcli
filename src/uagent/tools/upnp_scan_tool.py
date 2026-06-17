from __future__ import annotations

import json
import socket
import time
from typing import Any

from ._upnp_shared import (
    _MSEARCH_ADDR,
    extract_device_items,
    extract_host,
    extract_uuid,
    fetch_url_text,
)
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:upnp_scan"

_DEFAULT_MX = 3
_DEFAULT_WAIT_TIMEOUT = 4
_DEFAULT_TIMEOUT = _DEFAULT_WAIT_TIMEOUT
_DEFAULT_RETRY = 1
_DEFAULT_LIMIT = 50
_DEFAULT_SEARCH_TARGET = "ssdp:all"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "iot",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "upnp_scan",
        "description": _(
            "tool.description",
            default=(
                "Discover UPnP/SSDP devices on the local network and return a JSON or text list. "
                "Supports filtering by name, manufacturer, model, or device type."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mx": {
                    "type": "integer",
                    "default": _DEFAULT_MX,
                    "description": _(
                        "param.mx.description",
                        default="SSDP MX header value (1-5 seconds) used by M-SEARCH.",
                    ),
                },
                "wait_timeout": {
                    "type": "integer",
                    "default": _DEFAULT_WAIT_TIMEOUT,
                    "description": _(
                        "param.wait_timeout.description",
                        default="Client-side wait time in seconds for SSDP responses.",
                    ),
                },
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default="Optional local interface IPv4 address or interface name to bind to.",
                    ),
                },
                "retry": {
                    "type": "integer",
                    "default": _DEFAULT_RETRY,
                    "description": _(
                        "param.retry.description",
                        default="How many SSDP discovery rounds to send before returning.",
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_LIMIT,
                    "description": _(
                        "param.limit.description",
                        default="Maximum number of devices to return.",
                    ),
                },
                "search_target": {
                    "type": "string",
                    "default": _DEFAULT_SEARCH_TARGET,
                    "description": _(
                        "param.search_target.description",
                        default="SSDP search target (ST), e.g. 'ssdp:all' or 'upnp:rootdevice'.",
                    ),
                },
                "filter_name": {
                    "type": "string",
                    "description": _(
                        "param.filter_name.description",
                        default="Optional case-insensitive substring filter for friendly_name.",
                    ),
                },
                "filter_manufacturer": {
                    "type": "string",
                    "description": _(
                        "param.filter_manufacturer.description",
                        default="Optional case-insensitive substring filter for manufacturer.",
                    ),
                },
                "filter_model": {
                    "type": "string",
                    "description": _(
                        "param.filter_model.description",
                        default="Optional case-insensitive substring filter for model_name.",
                    ),
                },
                "filter_type": {
                    "type": "string",
                    "description": _(
                        "param.filter_type.description",
                        default="Optional case-insensitive substring filter for device_type.",
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
            _(
                "err.invalid_interface",
                default="Error: Could not resolve interface '{interface}' to a local IPv4 address.",
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
            _score, best_name, best_ip = candidates[0]
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


def _build_msearch(search_target: str, mx: int) -> bytes:
    mx = max(1, min(mx, 5))
    lines = [
        "M-SEARCH * HTTP/1.1",
        f"HOST: {_MSEARCH_ADDR[0]}:{_MSEARCH_ADDR[1]}",
        'MAN: "ssdp:discover"',
        f"MX: {mx}",
        f"ST: {search_target or _DEFAULT_SEARCH_TARGET}",
        "",
        "",
    ]
    return "\r\n".join(lines).encode("ascii")


def _parse_ssdp_response(raw: bytes) -> dict[str, str]:
    text = raw.decode("utf-8", errors="ignore")
    headers: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _format_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(
        _(
            "msg.summary",
            default="UPnP discovery completed: {count} device(s) found in {elapsed_ms} ms.",
            count=payload.get("count", 0),
            elapsed_ms=payload.get("elapsed_ms", 0),
        )
    )
    mx = payload.get("mx")
    wait_timeout = payload.get("wait_timeout")
    if mx is not None:
        lines.append(f"MX: {mx}")
    if wait_timeout is not None:
        lines.append(f"Wait timeout: {wait_timeout} s")
    interface_used = payload.get("interface_used")
    if interface_used:
        lines.append(f"Interface: {interface_used}")
    search_target = payload.get("search_target")
    if search_target:
        lines.append(f"ST: {search_target}")
    filters = payload.get("filters", {})
    active_filters = {k: v for k, v in filters.items() if v}
    if active_filters:
        lines.append(f"Filters: {active_filters}")
    lines.append("")

    items = payload.get("items") or []
    if not items:
        lines.append(_("msg.no_devices", default="No UPnP devices were found."))
        return "\n".join(lines).strip()

    for idx, item in enumerate(items, 1):
        name = item.get("friendly_name") or item.get("model_name") or "(unknown)"
        lines.append(f"[{idx}] {name}")
        if item.get("manufacturer"):
            lines.append(f"  manufacturer: {item.get('manufacturer')}")
        if item.get("model_name"):
            lines.append(f"  model: {item.get('model_name')}")
        if item.get("device_type"):
            lines.append(f"  type: {item.get('device_type')}")
        if item.get("uuid"):
            lines.append(f"  uuid: {item.get('uuid')}")
        if item.get("ip"):
            lines.append(f"  ip: {item.get('ip')}")
        if item.get("location"):
            lines.append(f"  location: {item.get('location')}")
        if item.get("presentation_url"):
            lines.append(f"  presentation_url: {item.get('presentation_url')}")
        if item.get("server"):
            lines.append(f"  server: {item.get('server')}")
        services = item.get("services") or []
        lines.append(f"  services: {len(services)}")
        for svc in services[:5]:
            label = svc.get("service_type") or svc.get("service_id") or "(service)"
            lines.append(f"    - {label}")
        if len(services) > 5:
            lines.append(f"    ... and {len(services) - 5} more")
        description_error = item.get("description_error")
        if description_error:
            lines.append(f"  description_error: {description_error}")
        lines.append("")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    mx = _normalize_int(args.get("mx", _DEFAULT_MX), _DEFAULT_MX)
    wait_timeout = _normalize_int(
        args.get("wait_timeout", _DEFAULT_WAIT_TIMEOUT), _DEFAULT_WAIT_TIMEOUT
    )
    retry = _normalize_int(args.get("retry", _DEFAULT_RETRY), _DEFAULT_RETRY)
    limit = _normalize_int(args.get("limit", _DEFAULT_LIMIT), _DEFAULT_LIMIT)
    search_target = (
        str(args.get("search_target") or _DEFAULT_SEARCH_TARGET).strip()
        or _DEFAULT_SEARCH_TARGET
    )
    output_format = str(args.get("fmt") or "json").strip().lower()
    interface_arg = args.get("interface")
    interface = str(interface_arg).strip() if interface_arg is not None else ""

    filter_name = str(args.get("filter_name") or "").strip().lower() or None
    filter_manufacturer = (
        str(args.get("filter_manufacturer") or "").strip().lower() or None
    )
    filter_model = str(args.get("filter_model") or "").strip().lower() or None
    filter_type = str(args.get("filter_type") or "").strip().lower() or None

    if mx < 1:
        mx = _DEFAULT_MX
    if wait_timeout < 1:
        wait_timeout = _DEFAULT_WAIT_TIMEOUT
    if retry < 1:
        retry = _DEFAULT_RETRY
    if limit < 1:
        limit = _DEFAULT_LIMIT

    start_time = time.monotonic()

    try:
        bind_ip, interface_used = _resolve_interface(interface)
        raw_devices: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        discovery_packet = _build_msearch(search_target, mx)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
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
                    socket.IPPROTO_IP,
                    socket.IP_MULTICAST_IF,
                    socket.inet_aton(bind_ip),
                )
            except Exception:
                pass
        else:
            sock.bind(("0.0.0.0", 0))
        sock.settimeout(0.25)

        try:
            for attempt in range(retry):
                sock.sendto(discovery_packet, _MSEARCH_ADDR)
                deadline = time.monotonic() + wait_timeout
                while time.monotonic() < deadline:
                    try:
                        data, source = sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    headers = _parse_ssdp_response(data)
                    location = headers.get("location")
                    usn = headers.get("usn") or ""
                    st = headers.get("st") or ""
                    source_ip = source[0] if source else ""
                    key = (
                        location.lower() if location else "",
                        usn.lower(),
                        source_ip,
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    raw_devices.append(
                        {
                            "source_address": source_ip or None,
                            "st": st or None,
                            "usn": usn or None,
                            "location": location or None,
                            "server": headers.get("server"),
                            "cache_control": headers.get("cache-control"),
                            "raw_headers": headers,
                        }
                    )
                    if len(raw_devices) >= limit * 2:
                        break
                if len(raw_devices) >= limit * 2:
                    break
                if attempt + 1 < retry:
                    time.sleep(0.15)
        finally:
            sock.close()

        items: list[dict[str, Any]] = []
        desc_timeout = max(1, min(wait_timeout, 5))
        for raw_item in raw_devices:
            location = raw_item.get("location")
            item: dict[str, Any] = {
                "source_address": raw_item.get("source_address"),
                "ip": extract_host(location) or raw_item.get("source_address"),
                "st": raw_item.get("st"),
                "usn": raw_item.get("usn"),
                "location": location,
                "server": raw_item.get("server"),
                "cache_control": raw_item.get("cache_control"),
                "friendly_name": None,
                "manufacturer": None,
                "model_name": None,
                "device_type": None,
                "uuid": extract_uuid(raw_item.get("usn") or ""),
                "presentation_url": None,
                "serial_number": None,
                "model_number": None,
                "services": [],
                "description_status": "not_fetched",
                "description_error": None,
            }
            if location:
                try:
                    body, _headers = fetch_url_text(location, timeout=desc_timeout)
                    desc_info, services, _tree = extract_device_items(body, location)
                    item.update({k: v for k, v in desc_info.items() if k != "services"})
                    item["services"] = services
                    item["description_status"] = "ok"
                except Exception as exc:
                    item["description_status"] = "error"
                    item["description_error"] = str(exc)

            # Apply filters
            if filter_name:
                val = (item.get("friendly_name") or "").lower()
                if filter_name not in val:
                    continue
            if filter_manufacturer:
                val = (item.get("manufacturer") or "").lower()
                if filter_manufacturer not in val:
                    continue
            if filter_model:
                val = (item.get("model_name") or "").lower()
                if filter_model not in val:
                    continue
            if filter_type:
                val = (item.get("device_type") or "").lower()
                if filter_type not in val:
                    continue

            items.append(item)
            if len(items) >= limit:
                break

        payload: dict[str, Any] = {
            "ok": True,
            "count": len(items),
            "items": items,
            "interface_used": interface_used,
            "bind_ip": bind_ip,
            "search_target": search_target,
            "mx": mx,
            "wait_timeout": wait_timeout,
            "retry": retry,
            "limit": limit,
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if any([filter_name, filter_manufacturer, filter_model, filter_type]):
            payload["filters"] = {
                "filter_name": filter_name,
                "filter_manufacturer": filter_manufacturer,
                "filter_model": filter_model,
                "filter_type": filter_type,
            }

        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        err_payload = {
            "ok": False,
            "error": str(exc),
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
