from __future__ import annotations

"""UPnP device info tool.

Fetches and displays detailed information about a specific UPnP device
by its description URL (location) or IP address, including service list
and device tree (sub-devices).
"""

import json
from typing import Any

from ._upnp_shared import (
    extract_device_items,
    extract_host,
    fetch_url_text,
    make_device_text_summary,
)
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:upnp_device_info"

_DEFAULT_TIMEOUT = 5

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "iot",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "upnp_device_info",
        "description": _(
            "tool.description",
            default=(
                "Get detailed info about a specific UPnP device by its description URL (location) "
                "or IP address. Returns device metadata, service list, and device tree (sub-devices)."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": _(
                        "param.location.description",
                        default="UPnP device description URL (e.g. http://192.168.1.100:5000/description.xml).",
                    ),
                },
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Device IP address (used with optional port to build a description URL).",
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": 5000,
                    "description": _(
                        "param.port.description",
                        default="Port number (used with ip). Default: 5000 (common UPnP port).",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "description": _(
                        "param.timeout.description",
                        default="HTTP fetch timeout in seconds.",
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


def run_tool(args: dict[str, Any]) -> str:
    location = str(args.get("location") or "").strip()
    ip = str(args.get("ip") or "").strip()
    port = int(args.get("port", 5000))
    timeout = int(args.get("timeout", _DEFAULT_TIMEOUT))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if timeout < 1:
        timeout = _DEFAULT_TIMEOUT

    # Build URL from ip:port if location not given
    if not location:
        if not ip:
            payload = {
                "ok": False,
                "error": _(
                    "err.no_target",
                    default="Either 'location' or 'ip' must be provided.",
                ),
            }
            if output_format == "text":
                return f"Error: {payload['error']}"
            return json.dumps(payload, ensure_ascii=False)
        location = f"http://{ip}:{port}/description.xml"

    try:
        body, resp_headers = fetch_url_text(location, timeout=timeout)
        info, services, tree = extract_device_items(body, location)

        result: dict[str, Any] = {
            "ok": True,
            "location": location,
            "ip": extract_host(location),
            "device_info": info,
            "services": services,
            "device_tree": tree,
            "service_count": len(services),
        }

        if output_format == "text":
            lines: list[str] = []
            lines.append(
                _(
                    "msg.device_info",
                    default="Device info for {location}",
                    location=location,
                )
            )
            lines.append("")
            lines.extend(make_device_text_summary(info, tree))
            return "\n".join(lines).strip()

        return json.dumps(result, ensure_ascii=False)

    except Exception as exc:
        err_payload = {
            "ok": False,
            "location": location,
            "error": str(exc),
        }
        if output_format == "text":
            return f"Error fetching {location}: {exc}"
        return json.dumps(err_payload, ensure_ascii=False)
