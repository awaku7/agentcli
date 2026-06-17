from __future__ import annotations

"""Shared UPnP helpers for upnp_scan and upnp_device_info tools."""

import urllib.request
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urljoin, urlparse

_MSEARCH_ADDR = ("239.255.255.250", 1900)
_DEFAULT_USER_AGENT = "uag-upnp/1.0"


def extract_uuid(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    idx = lower.find("uuid:")
    if idx >= 0:
        text = text[idx + 5 :]
    if "::" in text:
        text = text.split("::", 1)[0]
    return text.strip() or None


def safe_join(base: str | None, url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if base:
        return urljoin(base, url)
    return url


def extract_host(location: str | None) -> str | None:
    if not location:
        return None
    try:
        parsed = urlparse(location)
        return parsed.hostname
    except Exception:
        return None


def fetch_url_text(location: str, timeout: int) -> tuple[str, dict[str, str]]:
    request = urllib.request.Request(
        location,
        headers={"User-Agent": _DEFAULT_USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(1_000_000).decode(charset, errors="replace")
        return body, {k.lower(): v for k, v in response.headers.items()}


def _find_text(device_elem: ET.Element | None, name: str) -> str | None:
    """Find a text value by tag name under a device element."""
    if device_elem is None:
        return None
    try:
        value = device_elem.findtext(f"./{{*}}{name}")
    except Exception:
        return None
    if value:
        value = value.strip()
        if value:
            return value
    return None


def _extract_services_from_device(
    device_elem: ET.Element, base_url: str | None
) -> list[dict[str, Any]]:
    """Extract service list from a device element."""
    services: list[dict[str, Any]] = []
    service_elements = device_elem.findall("./{*}serviceList/{*}service")
    seen_keys: set[tuple] = set()
    for svc in service_elements:
        service_type = (svc.findtext("./{*}serviceType") or "").strip() or None
        service_id = (svc.findtext("./{*}serviceId") or "").strip() or None
        control_url = safe_join(
            base_url, (svc.findtext("./{*}controlURL") or "").strip() or None
        )
        event_sub_url = safe_join(
            base_url, (svc.findtext("./{*}eventSubURL") or "").strip() or None
        )
        scpd_url = safe_join(
            base_url, (svc.findtext("./{*}SCPDURL") or "").strip() or None
        )
        key = (service_type, service_id, control_url, event_sub_url, scpd_url)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if any([service_type, service_id, control_url, event_sub_url, scpd_url]):
            services.append(
                {
                    "service_type": service_type,
                    "service_id": service_id,
                    "control_url": control_url,
                    "event_sub_url": event_sub_url,
                    "scpd_url": scpd_url,
                }
            )
    return services


def _extract_device_tree(
    device_elem: ET.Element, base_url: str | None
) -> list[dict[str, Any]]:
    """Recursively extract embedded sub-devices (deviceList)."""
    children: list[dict[str, Any]] = []
    for child in device_elem.findall("./{*}deviceList/{*}device"):
        node = _extract_device_info(child, base_url)
        children.append(node)
    return children


def _extract_device_info(
    device_elem: ET.Element, base_url: str | None
) -> dict[str, Any]:
    """Extract full info from a single device element (may include sub-devices)."""
    info = {
        "friendly_name": _find_text(device_elem, "friendlyName"),
        "manufacturer": _find_text(device_elem, "manufacturer"),
        "model_name": _find_text(device_elem, "modelName"),
        "model_number": _find_text(device_elem, "modelNumber"),
        "device_type": _find_text(device_elem, "deviceType"),
        "udn": _find_text(device_elem, "UDN") or _find_text(device_elem, "uuid"),
        "serial_number": _find_text(device_elem, "serialNumber"),
        "presentation_url": safe_join(
            base_url, _find_text(device_elem, "presentationURL")
        ),
        "services": _extract_services_from_device(device_elem, base_url),
        "sub_devices": _extract_device_tree(device_elem, base_url),
    }
    info["uuid"] = extract_uuid(info.get("udn"))
    return info


def extract_device_items(
    xml_text: str,
    base_url: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Parse UPnP device description XML.

    Returns (flat_info, services, device_tree).
    - flat_info: top-level device fields (same as before, for backward compat)
    - services: all services from the root device
    - device_tree: full recursive structure including sub-devices
    """
    root = ET.fromstring(xml_text)
    device = root if root.tag.endswith("device") else root.find("./{*}device")
    if device is None:
        device = root.find(".//{*}device")

    if device is None:
        return {}, [], {"error": "No device element found in XML"}

    # Flat info (backward compatible)
    info = {
        "friendly_name": _find_text(device, "friendlyName"),
        "manufacturer": _find_text(device, "manufacturer"),
        "model_name": _find_text(device, "modelName"),
        "model_number": _find_text(device, "modelNumber"),
        "device_type": _find_text(device, "deviceType"),
        "uuid": extract_uuid(_find_text(device, "UDN") or _find_text(device, "uuid")),
        "presentation_url": safe_join(base_url, _find_text(device, "presentationURL")),
        "serial_number": _find_text(device, "serialNumber"),
        "services": [],
    }

    # Services and tree
    services = _extract_services_from_device(device, base_url)
    info["services"] = services

    tree = _extract_device_info(device, base_url)

    return info, services, tree


def make_device_text_summary(
    info: dict[str, Any], tree: dict[str, Any] | None, indent: int = 0
) -> list[str]:
    """Format device info as text lines."""
    prefix = "  " * indent
    lines: list[str] = []
    name = info.get("friendly_name") or info.get("model_name") or "(unknown)"
    lines.append(f"{prefix}{name}")
    if info.get("manufacturer"):
        lines.append(f"{prefix}  manufacturer: {info['manufacturer']}")
    if info.get("model_name"):
        lines.append(f"{prefix}  model: {info['model_name']}")
    if info.get("model_number"):
        lines.append(f"{prefix}  model_number: {info['model_number']}")
    if info.get("device_type"):
        lines.append(f"{prefix}  type: {info['device_type']}")
    if info.get("uuid"):
        lines.append(f"{prefix}  uuid: {info['uuid']}")
    if info.get("serial_number"):
        lines.append(f"{prefix}  serial: {info['serial_number']}")
    if info.get("presentation_url"):
        lines.append(f"{prefix}  presentation_url: {info['presentation_url']}")

    services = info.get("services") or []
    if services:
        lines.append(f"{prefix}  services: {len(services)}")
        for svc in services:
            label = svc.get("service_type") or svc.get("service_id") or "(service)"
            lines.append(f"{prefix}    - {label}")

    sub_devices = (tree or info).get("sub_devices") or []
    if sub_devices:
        lines.append(f"{prefix}  sub_devices: {len(sub_devices)}")
        for sd in sub_devices:
            lines.extend(make_device_text_summary(sd, sd, indent + 2))

    return lines
