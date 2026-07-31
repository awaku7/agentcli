from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:opcua_scan"

_DEFAULT_PORT = 4840
_DEFAULT_TIMEOUT = 3

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "opcua_scan",
        "description": _(
            "tool.description",
            default=(
                "Discover OPC UA servers on the local network. "
                "Probes IP addresses on the default OPC UA port (4840) "
                "and attempts to connect and read the server's endpoint info."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "opcua scan",
                "opcua_scan",
                "opcua",
                "OPCUA",
                "discover",
                "servers",
                "local",
                "network",
            ],
        ),
        "x_search_terms_en": [
            "opcua scan",
            "opcua_scan",
            "opcua",
            "OPCUA",
            "discover",
            "servers",
            "local",
            "network",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "ip_range": {
                    "type": "string",
                    "description": _(
                        "param.ip_range.description",
                        default="IP range (e.g. '192.168.1.1-254' or '192.168.1.0/24').",
                    ),
                },
                "port": {
                    "type": "integer",
                    "default": _DEFAULT_PORT,
                    "description": _(
                        "param.port.description",
                        default="OPC UA port (default: 4840).",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout per connection (seconds).",
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


def _parse_ip_range(text: str) -> list[str]:
    text = text.strip()
    ips: list[str] = []
    if "/" in text:
        try:
            import ipaddress

            for host in ipaddress.ip_network(text, strict=False).hosts():
                ips.append(str(host))
            return ips
        except Exception:
            pass
    if "-" in text:
        parts = text.rsplit(".", 1)
        if len(parts) == 2:
            base = parts[0]
            range_part = parts[1]
            if "-" in range_part:
                try:
                    start_s, end_s = range_part.split("-", 1)
                    for i in range(int(start_s.strip()), int(end_s.strip()) + 1):
                        ips.append(f"{base}.{i}")
                    return ips
                except Exception:
                    pass
    try:
        socket.inet_aton(text)
        ips.append(text)
    except Exception:
        pass
    return ips


def _probe_ip(ip: str, port: int, timeout: int) -> dict[str, Any] | None:
    """Try to connect to an OPC UA endpoint and get server info."""
    import asyncio
    from asyncua import Client

    async def _try():
        try:
            c = Client(f"opc.tcp://{ip}:{port}", timeout=timeout)
            await c.connect()
            try:
                from asyncua import ua

                node_id = ua.NodeId(ua.ObjectIds.Server_ServerStatus_BuildInfo)
                bi = await c.read_node(node_id)
                return {"build_info": str(bi)}
            except Exception:
                return {"discovered": True}
            finally:
                await c.disconnect()
        except Exception:
            return None

    try:
        return asyncio.run(_try())
    except Exception:
        return None


def _format_text(payload: dict[str, Any]) -> str:
    servers = payload.get("servers") or []
    lines = [
        _(
            "msg.summary",
            default="OPC UA scan: {count} server(s) found in {ms} ms.",
            count=len(servers),
            ms=payload.get("elapsed_ms", 0),
        )
    ]
    if not servers:
        lines.append(_("msg.no_servers", default="No OPC UA servers were found."))
        return "\n".join(lines).strip()
    for idx, s in enumerate(servers, 1):
        lines.append(f"[{idx}] {s.get('url')}")
        if s.get("build_info"):
            lines.append(f"  build: {s.get('build_info')[:80]}")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_range = str(args.get("ip_range") or "").strip()
    port = int(args.get("port", _DEFAULT_PORT))
    timeout = int(args.get("timeout", _DEFAULT_TIMEOUT))
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip_range:
        err = _(
            "err.ip_range_required",
            default="ip_range is required (e.g. '192.168.1.1-254').",
        )
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    ips = _parse_ip_range(ip_range)
    if not ips:
        err = _(
            "err.invalid_ip_range",
            default="Could not parse ip_range: {text}",
            text=ip_range,
        )
        return json.dumps({"ok": False, "error": err}, ensure_ascii=False)

    start_time = time.monotonic()
    servers: list[dict[str, Any]] = []

    for ip in ips:
        try:
            # TCP port check first (fast)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result != 0:
                continue
        except Exception:
            continue

        info = _probe_ip(ip, port, timeout)
        if info is not None:
            servers.append(
                {
                    "url": f"opc.tcp://{ip}:{port}",
                    "ip": ip,
                    "port": port,
                    "build_info": info.get("build_info"),
                    "last_seen": _now_iso(),
                }
            )

    payload = {
        "ok": True,
        "count": len(servers),
        "servers": servers,
        "ip_range": ip_range,
        "ips_scanned": len(ips),
        "elapsed_ms": int((time.monotonic() - start_time) * 1000),
    }

    if output_format == "text":
        return _format_text(payload)
    return json.dumps(payload, ensure_ascii=False)
