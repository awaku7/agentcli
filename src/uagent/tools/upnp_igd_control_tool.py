from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from .i18n_helper import make_tool_translator
from .upnp_scan_tool import (
    _DEFAULT_LIMIT,
    _DEFAULT_RETRY,
    _DEFAULT_WAIT_TIMEOUT as _DEFAULT_TIMEOUT,
    _DEFAULT_USER_AGENT,
    _normalize_int,
    run_tool as _scan_run_tool,
)

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:upnp_igd_control"

_DEFAULT_IGD_SEARCH_TARGET = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "upnp_igd_control",
        "description": _(
            "tool.description",
            default=(
                "Perform UPnP IGD router operations: inspect WAN status, list port mappings, add a port mapping, or delete a port mapping."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "portmap_list", "portmap_add", "portmap_delete"],
                    "description": _(
                        "param.action.description",
                        default=(
                            "Operation to perform: status, portmap_list, portmap_add, or portmap_delete."
                        ),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout in seconds for discovery and SOAP requests.",
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
                        default="Maximum number of port mapping entries to return.",
                    ),
                },
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default=(
                            "Optional local interface IPv4 address or interface name to bind to."
                        ),
                    ),
                },
                "search_target": {
                    "type": "string",
                    "default": _DEFAULT_IGD_SEARCH_TARGET,
                    "description": _(
                        "param.search_target.description",
                        default=(
                            "SSDP search target (ST) for discovery. Defaults to InternetGatewayDevice and falls back to ssdp:all if needed."
                        ),
                    ),
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.output_format.description",
                        default="Output format: JSON or human-readable text.",
                    ),
                },
                "external_port": {
                    "type": "integer",
                    "description": _(
                        "param.external_port.description",
                        default="External port number for port mapping add/delete operations.",
                    ),
                },
                "internal_ip": {
                    "type": "string",
                    "description": _(
                        "param.internal_ip.description",
                        default=(
                            "Internal LAN IP address that should receive the forwarded traffic."
                        ),
                    ),
                },
                "internal_port": {
                    "type": "integer",
                    "description": _(
                        "param.internal_port.description",
                        default="Internal port number for port mapping add operations.",
                    ),
                },
                "protocol": {
                    "type": "string",
                    "enum": ["TCP", "UDP"],
                    "default": "TCP",
                    "description": _(
                        "param.protocol.description",
                        default="Protocol for port mapping: TCP or UDP.",
                    ),
                },
                "description": {
                    "type": "string",
                    "description": _(
                        "param.description.description",
                        default="Port mapping description used for add operations.",
                    ),
                },
                "lease_duration": {
                    "type": "integer",
                    "default": 0,
                    "description": _(
                        "param.lease_duration.description",
                        default="Lease duration in seconds for port mapping add operations. 0 means indefinite on most routers.",
                    ),
                },
                "remote_host": {
                    "type": "string",
                    "description": _(
                        "param.remote_host.description",
                        default=(
                            "Optional remote host filter for specific port mapping operations. Leave empty for all hosts."
                        ),
                    ),
                },
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.enabled.description",
                        default="Whether the port mapping should be enabled when adding a rule.",
                    ),
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}

_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"


def _is_ipv4_address(value: str) -> bool:
    try:
        import socket

        socket.inet_aton(value)
        return value.count(".") == 3
    except Exception:
        return False


def _bool_from_text(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _int_from_text(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _safe_device_copy(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    out.pop("raw_headers", None)
    return out


def _scan_devices(
    interface: str,
    timeout: int,
    retry: int,
    limit: int,
    search_target: str,
) -> dict[str, Any]:
    scan_args = {
        "timeout": timeout,
        "interface": interface,
        "retry": retry,
        "limit": limit,
        "search_target": search_target,
        "output_format": "json",
    }
    scan_text = _scan_run_tool(scan_args)
    try:
        payload = json.loads(scan_text)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse UPnP scan output: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("UPnP scan output was not a JSON object.")
    if not payload.get("ok", False):
        raise RuntimeError(str(payload.get("error") or "UPnP scan failed."))
    return payload


def _is_igd_candidate(item: dict[str, Any]) -> bool:
    device_type = str(item.get("device_type") or "")
    if "InternetGatewayDevice" in device_type:
        return True
    for service in item.get("services") or []:
        service_type = str(service.get("service_type") or "")
        if "WANIPConnection" in service_type or "WANPPPConnection" in service_type:
            return True
    return False


def _select_igd_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if _is_igd_candidate(item):
            candidates.append(item)
    return candidates


def _service_supports_port_mapping(service: dict[str, Any] | None) -> bool:
    if not isinstance(service, dict):
        return False
    service_type = str(service.get("service_type") or "")
    return "WANIPConnection" in service_type or "WANPPPConnection" in service_type


def _service_is_layer3_forwarding(service: dict[str, Any] | None) -> bool:
    if not isinstance(service, dict):
        return False
    service_type = str(service.get("service_type") or "")
    return "Layer3Forwarding" in service_type


def _service_matches_identifier(service: dict[str, Any] | None, identifier: Any) -> bool:
    if not isinstance(service, dict):
        return False
    needle = str(identifier or "").strip()
    if not needle:
        return False
    needle_low = needle.lower()
    for field in ("service_id", "service_type", "control_url"):
        value = str(service.get(field) or "").strip()
        if not value:
            continue
        value_low = value.lower()
        if needle == value or needle_low == value_low or needle_low in value_low or value_low in needle_low:
            return True
    return False


def _select_igd_service(item: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    services = item.get("services") or []
    preferred: dict[str, Any] | None = None
    layer3_service: dict[str, Any] | None = None
    for service in services:
        if not isinstance(service, dict):
            continue
        if _service_supports_port_mapping(service):
            if service.get("control_url"):
                return service
            preferred = preferred or service
        elif _service_is_layer3_forwarding(service) and service.get("control_url"):
            layer3_service = layer3_service or service
    if preferred and preferred.get("control_url"):
        return preferred
    if layer3_service:
        try:
            values = _call_service_action(layer3_service, "GetDefaultConnectionService", {}, timeout)
        except Exception:
            return None
        default_id = values.get("NewDefaultConnectionService") or values.get("DefaultConnectionService")
        if default_id:
            for service in services:
                if _service_matches_identifier(service, default_id) and _service_supports_port_mapping(service):
                    if service.get("control_url"):
                        return service
    return None


def _soap_envelope(service_type: str, action: str, arguments: dict[str, Any]) -> bytes:
    arg_xml = []
    for key, value in arguments.items():
        text = "" if value is None else str(value)
        arg_xml.append(f"      <{key}>{xml_escape(text)}</{key}>")
    body = "\n".join(arg_xml)
    xml = (
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<s:Envelope xmlns:s="{_SOAP_NS}" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\n'
        f"  <s:Body>\n"
        f'    <u:{action} xmlns:u="{service_type}">\n'
        f"{body}\n"
        f"    </u:{action}>\n"
        f"  </s:Body>\n"
        f"</s:Envelope>"
    )
    return xml.encode("utf-8")


def _soap_fault_details(xml_text: str) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return None, None
    code = root.findtext(".//{*}errorCode")
    desc = root.findtext(".//{*}errorDescription")
    return (code.strip() if code else None, desc.strip() if desc else None)


def _soap_response_values(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    body = root.find(".//{*}Body")
    if body is None:
        body = root

    for child in list(body):
        values: dict[str, Any] = {}
        for elem in list(child):
            key = elem.tag.rsplit("}", 1)[-1]
            if elem.text is None:
                values[key] = None
            else:
                values[key] = elem.text.strip()
        if values:
            return values
    return {}


def _soap_call(
    control_url: str,
    service_type: str,
    action: str,
    arguments: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        control_url,
        data=_soap_envelope(service_type, action, arguments),
        headers={
            "User-Agent": _DEFAULT_USER_AGENT,
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{service_type}#{action}"',
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(1_000_000).decode(charset, errors="replace")
            return {
                "ok": True,
                "text": body,
                "status": getattr(response, "status", 200),
                "headers": {k.lower(): v for k, v in response.headers.items()},
            }
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(1_000_000).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        code, desc = _soap_fault_details(body)
        message = f"HTTP {exc.code}: {exc.reason}"
        if code or desc:
            message = f"SOAP fault {code or '?'}: {desc or message}"
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc)) from exc


def _call_service_action(
    service: dict[str, Any],
    action: str,
    arguments: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    control_url = service.get("control_url")
    service_type = service.get("service_type")
    if not control_url or not service_type:
        raise RuntimeError("IGD service is missing control_url or service_type.")
    result = _soap_call(str(control_url), str(service_type), action, arguments, timeout)
    if not result.get("ok"):
        raise RuntimeError("SOAP request failed.")
    return _soap_response_values(str(result.get("text") or ""))


def _find_igd_data(
    interface: str,
    timeout: int,
    retry: int,
    limit: int,
    search_target: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    attempts = []
    first_target = search_target or _DEFAULT_IGD_SEARCH_TARGET
    attempts.append(first_target)
    if first_target != "ssdp:all":
        attempts.append("ssdp:all")

    last_error: str | None = None
    for target in attempts:
        try:
            scan_payload = _scan_devices(interface, timeout, retry, limit, target)
        except Exception as exc:
            last_error = str(exc)
            continue
        items = scan_payload.get("items") or []
        if not isinstance(items, list):
            items = []
        candidates = _select_igd_candidates(
            [item for item in items if isinstance(item, dict)]
        )
        if candidates:
            return scan_payload, candidates, target
        last_error = _(
            "msg.no_igd_candidates",
            default="No IGD-capable UPnP devices were found in discovery results.",
        )
    raise RuntimeError(last_error or "No IGD-capable UPnP devices were found.")


def _format_service_summary(service: dict[str, Any] | None) -> dict[str, Any] | None:
    if not service:
        return None
    return {
        "service_type": service.get("service_type"),
        "service_id": service.get("service_id"),
        "control_url": service.get("control_url"),
        "event_sub_url": service.get("event_sub_url"),
        "scpd_url": service.get("scpd_url"),
    }


def _format_text(payload: dict[str, Any]) -> str:
    action = payload.get("action") or "status"
    lines: list[str] = []
    if action == "status":
        lines.append(
            _(
                "msg.status.summary",
                default="UPnP IGD status completed in {elapsed_ms} ms.",
                elapsed_ms=payload.get("elapsed_ms", 0),
            )
        )
        device = payload.get("device") or {}
        if device.get("friendly_name"):
            lines.append(f"Device: {device.get('friendly_name')}")
        if payload.get("external_ip"):
            lines.append(f"External IP: {payload.get('external_ip')}")
        if payload.get("connection_status"):
            lines.append(f"Connection status: {payload.get('connection_status')}")
        if payload.get("connection_type"):
            lines.append(f"Connection type: {payload.get('connection_type')}")
        if payload.get("uptime") is not None:
            lines.append(f"Uptime: {payload.get('uptime')}")
        lines.append(
            f"Supports port mapping: {bool(payload.get('supports_port_mapping'))}"
        )
    elif action == "portmap_list":
        lines.append(
            _(
                "msg.portmap.summary",
                default="UPnP IGD port mapping list: {count} item(s) in {elapsed_ms} ms.",
                count=payload.get("count", 0),
                elapsed_ms=payload.get("elapsed_ms", 0),
            )
        )
        device = payload.get("device") or {}
        if device.get("friendly_name"):
            lines.append(f"Device: {device.get('friendly_name')}")
        items = payload.get("items") or []
        if not items:
            lines.append(_("msg.no_portmaps", default="No port mappings were found."))
        for idx, item in enumerate(items, 1):
            ext_port = item.get("external_port")
            proto = item.get("protocol") or "?"
            internal_ip = item.get("internal_ip") or "?"
            internal_port = item.get("internal_port") or "?"
            desc = item.get("description") or ""
            enabled = "on" if item.get("enabled") else "off"
            lines.append(
                f"[{idx}] {proto} {ext_port} -> {internal_ip}:{internal_port} ({enabled}) {desc}".rstrip()
            )
    elif action == "portmap_add":
        lines.append(
            _(
                "msg.portmap_add.summary",
                default="Port mapping add completed in {elapsed_ms} ms.",
                elapsed_ms=payload.get("elapsed_ms", 0),
            )
        )
        if payload.get("added"):
            lines.append("Added: yes")
        if payload.get("internal_ip"):
            lines.append(f"Internal IP: {payload.get('internal_ip')}")
        if payload.get("internal_port") is not None:
            lines.append(f"Internal port: {payload.get('internal_port')}")
        if payload.get("external_port") is not None:
            lines.append(f"External port: {payload.get('external_port')}")
        if payload.get("protocol"):
            lines.append(f"Protocol: {payload.get('protocol')}")
    elif action == "portmap_delete":
        lines.append(
            _(
                "msg.portmap_delete.summary",
                default="Port mapping delete completed in {elapsed_ms} ms.",
                elapsed_ms=payload.get("elapsed_ms", 0),
            )
        )
        if payload.get("deleted"):
            lines.append("Deleted: yes")
        if payload.get("external_port") is not None:
            lines.append(f"External port: {payload.get('external_port')}")
        if payload.get("protocol"):
            lines.append(f"Protocol: {payload.get('protocol')}")
    else:
        lines.append(str(payload))

    warnings_list = payload.get("warnings") or []
    if warnings_list:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings_list:
            lines.append(f"- {warning}")

    error = payload.get("error")
    if error:
        lines.append("")
        lines.append(f"Error: {error}")

    return "\n".join(lines).strip()


def _run_status(
    interface: str,
    timeout: int,
    retry: int,
    limit: int,
    search_target: str,
) -> dict[str, Any]:
    scan_payload, candidates, used_target = _find_igd_data(
        interface=interface,
        timeout=timeout,
        retry=retry,
        limit=limit,
        search_target=search_target,
    )
    device = _safe_device_copy(candidates[0])
    service = _select_igd_service(device, timeout)
    if not service:
        raise RuntimeError("No WANIPConnection or WANPPPConnection service was found.")

    warnings_list: list[str] = []
    external_ip = None
    connection_status = None
    connection_type = None
    uptime = None

    try:
        values = _call_service_action(service, "GetExternalIPAddress", {}, timeout)
        external_ip = values.get("NewExternalIPAddress") or values.get(
            "ExternalIPAddress"
        )
    except Exception as exc:
        warnings_list.append(str(exc))

    try:
        values = _call_service_action(service, "GetStatusInfo", {}, timeout)
        connection_status = values.get("NewConnectionStatus") or values.get(
            "ConnectionStatus"
        )
        uptime = _int_from_text(values.get("NewUptime") or values.get("Uptime"))
    except Exception as exc:
        warnings_list.append(str(exc))

    try:
        values = _call_service_action(service, "GetConnectionTypeInfo", {}, timeout)
        connection_type = values.get("NewConnectionType") or values.get(
            "ConnectionType"
        )
    except Exception as exc:
        warnings_list.append(str(exc))

    payload = {
        "ok": True,
        "action": "status",
        "count": len(candidates),
        "scan_count": scan_payload.get("count", 0),
        "devices": [_safe_device_copy(item) for item in candidates],
        "device": device,
        "service": _format_service_summary(service),
        "search_target": used_target,
        "interface_used": scan_payload.get("interface_used"),
        "bind_ip": scan_payload.get("bind_ip"),
        "timeout": timeout,
        "retry": retry,
        "limit": limit,
        "external_ip": external_ip,
        "wan_ip": external_ip,
        "connection_status": connection_status,
        "connection_type": connection_type,
        "uptime": uptime,
        "supports_port_mapping": _service_supports_port_mapping(service),
        "warnings": warnings_list,
    }
    return payload


def _run_portmap_list(
    interface: str,
    timeout: int,
    retry: int,
    limit: int,
    search_target: str,
) -> dict[str, Any]:
    scan_payload, candidates, used_target = _find_igd_data(
        interface=interface,
        timeout=timeout,
        retry=retry,
        limit=limit,
        search_target=search_target,
    )
    device = _safe_device_copy(candidates[0])
    service = _select_igd_service(device, timeout)
    if not service:
        raise RuntimeError("No WANIPConnection or WANPPPConnection service was found.")

    items: list[dict[str, Any]] = []
    warnings_list: list[str] = []
    truncated = False

    for index in range(max(1, limit)):
        try:
            values = _call_service_action(
                service,
                "GetGenericPortMappingEntry",
                {"NewPortMappingIndex": index},
                timeout,
            )
        except Exception as exc:
            message = str(exc)
            if (
                "713" in message
                or "NoSuchEntryInArray" in message
                or "SpecifiedArrayIndexInvalid" in message
            ):
                break
            if not items:
                raise RuntimeError(message) from exc
            warnings_list.append(message)
            break

        entry = {
            "index": index,
            "remote_host": values.get("NewRemoteHost")
            or values.get("RemoteHost")
            or None,
            "external_port": _int_from_text(
                values.get("NewExternalPort") or values.get("ExternalPort")
            ),
            "protocol": values.get("NewProtocol") or values.get("Protocol") or None,
            "internal_port": _int_from_text(
                values.get("NewInternalPort") or values.get("InternalPort")
            ),
            "internal_ip": values.get("NewInternalClient")
            or values.get("InternalClient")
            or None,
            "enabled": _bool_from_text(
                values.get("NewEnabled") or values.get("Enabled")
            ),
            "description": values.get("NewPortMappingDescription")
            or values.get("PortMappingDescription")
            or None,
            "lease_duration": _int_from_text(
                values.get("NewLeaseDuration") or values.get("LeaseDuration")
            ),
        }
        items.append(entry)
        if len(items) >= limit:
            truncated = True
            break

    payload = {
        "ok": True,
        "action": "portmap_list",
        "count": len(items),
        "items": items,
        "truncated": truncated,
        "devices": [_safe_device_copy(item) for item in candidates],
        "device": device,
        "service": _format_service_summary(service),
        "scan_count": scan_payload.get("count", 0),
        "search_target": used_target,
        "interface_used": scan_payload.get("interface_used"),
        "bind_ip": scan_payload.get("bind_ip"),
        "timeout": timeout,
        "retry": retry,
        "limit": limit,
        "warnings": warnings_list,
    }
    return payload


def _validate_port(port_value: Any, field_name: str) -> int:
    port = _normalize_int(port_value, 0)
    if port < 1 or port > 65535:
        raise ValueError(f"{field_name} must be an integer between 1 and 65535.")
    return port


def _run_portmap_add(
    interface: str,
    timeout: int,
    retry: int,
    limit: int,
    search_target: str,
    external_port: Any,
    internal_ip: Any,
    internal_port: Any,
    protocol: Any,
    description: Any,
    lease_duration: Any,
    remote_host: Any,
    enabled: Any,
) -> dict[str, Any]:
    scan_payload, candidates, used_target = _find_igd_data(
        interface=interface,
        timeout=timeout,
        retry=retry,
        limit=limit,
        search_target=search_target,
    )
    device = _safe_device_copy(candidates[0])
    service = _select_igd_service(device, timeout)
    if not service:
        raise RuntimeError("No WANIPConnection or WANPPPConnection service was found.")

    bind_ip = scan_payload.get("bind_ip")
    internal_ip_text = str(internal_ip or bind_ip or "").strip()
    if not internal_ip_text:
        raise ValueError(
            "internal_ip is required (or select an interface that resolves to a local IPv4 address)."
        )
    if not _is_ipv4_address(internal_ip_text):
        raise ValueError(f"internal_ip is not a valid IPv4 address: {internal_ip_text}")

    external_port_num = _validate_port(external_port, "external_port")
    internal_port_num = _validate_port(internal_port, "internal_port")
    protocol_text = str(protocol or "TCP").strip().upper()
    if protocol_text not in {"TCP", "UDP"}:
        raise ValueError("protocol must be TCP or UDP.")

    lease_duration_num = _normalize_int(lease_duration, 0)
    desc_text = (
        str(description or "uag upnp port mapping").strip() or "uag upnp port mapping"
    )
    remote_host_text = str(remote_host or "").strip()
    enabled_flag = 1 if _bool_from_text(enabled, True) else 0

    _call_service_action(
        service,
        "AddPortMapping",
        {
            "NewRemoteHost": remote_host_text,
            "NewExternalPort": external_port_num,
            "NewProtocol": protocol_text,
            "NewInternalPort": internal_port_num,
            "NewInternalClient": internal_ip_text,
            "NewEnabled": enabled_flag,
            "NewPortMappingDescription": desc_text,
            "NewLeaseDuration": lease_duration_num,
        },
        timeout,
    )

    verified_entry = None
    try:
        values = _call_service_action(
            service,
            "GetSpecificPortMappingEntry",
            {
                "NewRemoteHost": remote_host_text,
                "NewExternalPort": external_port_num,
                "NewProtocol": protocol_text,
            },
            timeout,
        )
        verified_entry = {
            "remote_host": values.get("NewRemoteHost")
            or values.get("RemoteHost")
            or None,
            "external_port": _int_from_text(
                values.get("NewExternalPort") or values.get("ExternalPort")
            ),
            "protocol": values.get("NewProtocol") or values.get("Protocol") or None,
            "internal_port": _int_from_text(
                values.get("NewInternalPort") or values.get("InternalPort")
            ),
            "internal_ip": values.get("NewInternalClient")
            or values.get("InternalClient")
            or None,
            "enabled": _bool_from_text(
                values.get("NewEnabled") or values.get("Enabled")
            ),
            "description": values.get("NewPortMappingDescription")
            or values.get("PortMappingDescription")
            or None,
            "lease_duration": _int_from_text(
                values.get("NewLeaseDuration") or values.get("LeaseDuration")
            ),
        }
    except Exception:
        pass

    payload = {
        "ok": True,
        "action": "portmap_add",
        "added": True,
        "external_port": external_port_num,
        "internal_ip": internal_ip_text,
        "internal_port": internal_port_num,
        "protocol": protocol_text,
        "description": desc_text,
        "lease_duration": lease_duration_num,
        "remote_host": remote_host_text or None,
        "enabled": bool(enabled_flag),
        "verified_entry": verified_entry,
        "devices": [_safe_device_copy(item) for item in candidates],
        "device": device,
        "service": _format_service_summary(service),
        "scan_count": scan_payload.get("count", 0),
        "search_target": used_target,
        "interface_used": scan_payload.get("interface_used"),
        "bind_ip": scan_payload.get("bind_ip"),
        "timeout": timeout,
        "retry": retry,
        "limit": limit,
    }
    return payload


def _run_portmap_delete(
    interface: str,
    timeout: int,
    retry: int,
    limit: int,
    search_target: str,
    external_port: Any,
    protocol: Any,
    remote_host: Any,
) -> dict[str, Any]:
    scan_payload, candidates, used_target = _find_igd_data(
        interface=interface,
        timeout=timeout,
        retry=retry,
        limit=limit,
        search_target=search_target,
    )
    device = _safe_device_copy(candidates[0])
    service = _select_igd_service(device, timeout)
    if not service:
        raise RuntimeError("No WANIPConnection or WANPPPConnection service was found.")

    external_port_num = _validate_port(external_port, "external_port")
    protocol_text = str(protocol or "TCP").strip().upper()
    if protocol_text not in {"TCP", "UDP"}:
        raise ValueError("protocol must be TCP or UDP.")
    remote_host_text = str(remote_host or "").strip()

    _call_service_action(
        service,
        "DeletePortMapping",
        {
            "NewRemoteHost": remote_host_text,
            "NewExternalPort": external_port_num,
            "NewProtocol": protocol_text,
        },
        timeout,
    )

    payload = {
        "ok": True,
        "action": "portmap_delete",
        "deleted": True,
        "external_port": external_port_num,
        "protocol": protocol_text,
        "remote_host": remote_host_text or None,
        "devices": [_safe_device_copy(item) for item in candidates],
        "device": device,
        "service": _format_service_summary(service),
        "scan_count": scan_payload.get("count", 0),
        "search_target": used_target,
        "interface_used": scan_payload.get("interface_used"),
        "bind_ip": scan_payload.get("bind_ip"),
        "timeout": timeout,
        "retry": retry,
        "limit": limit,
    }
    return payload


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action") or "").strip().lower()
    timeout = _normalize_int(args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT)
    retry = _normalize_int(args.get("retry", _DEFAULT_RETRY), _DEFAULT_RETRY)
    limit = _normalize_int(args.get("limit", _DEFAULT_LIMIT), _DEFAULT_LIMIT)
    search_target = (
        str(args.get("search_target") or _DEFAULT_IGD_SEARCH_TARGET).strip()
        or _DEFAULT_IGD_SEARCH_TARGET
    )
    output_format = str(args.get("output_format") or "json").strip().lower()
    interface_arg = args.get("interface")
    interface = str(interface_arg).strip() if interface_arg is not None else ""

    if action not in {"status", "portmap_list", "portmap_add", "portmap_delete"}:
        message = _(
            "err.unknown_action",
            default="Error: Unknown action '{action}'.",
            action=action,
        )
        return (
            message
            if output_format == "text"
            else json.dumps({"ok": False, "error": message}, ensure_ascii=False)
        )

    if timeout < 1:
        timeout = _DEFAULT_TIMEOUT
    if retry < 1:
        retry = _DEFAULT_RETRY
    if limit < 1:
        limit = _DEFAULT_LIMIT

    start_time = time.monotonic()

    try:
        if action == "status":
            payload = _run_status(interface, timeout, retry, limit, search_target)
        elif action == "portmap_list":
            payload = _run_portmap_list(interface, timeout, retry, limit, search_target)
        elif action == "portmap_add":
            payload = _run_portmap_add(
                interface,
                timeout,
                retry,
                limit,
                search_target,
                args.get("external_port"),
                args.get("internal_ip"),
                args.get("internal_port"),
                args.get("protocol"),
                args.get("description"),
                args.get("lease_duration"),
                args.get("remote_host"),
                args.get("enabled"),
            )
        else:
            payload = _run_portmap_delete(
                interface,
                timeout,
                retry,
                limit,
                search_target,
                args.get("external_port"),
                args.get("protocol"),
                args.get("remote_host"),
            )

        payload["elapsed_ms"] = int((time.monotonic() - start_time) * 1000)
        if output_format == "text":
            return _format_text(payload)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        err_payload = {
            "ok": False,
            "action": action,
            "error": str(exc),
            "elapsed_ms": int((time.monotonic() - start_time) * 1000),
        }
        if output_format == "text":
            return f"Error: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
