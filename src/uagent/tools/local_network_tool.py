"""Cross-platform local network information using psutil."""

from __future__ import annotations

import json
from typing import Any

from .._pip_auto import install_with_status
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _get_psutil():
    try:
        import psutil

        return psutil
    except ImportError:
        if not install_with_status("psutil", "psutil", version_spec=">=5.9.0"):
            raise RuntimeError("psutil is unavailable")
        import psutil

        return psutil


def _error(code: str, message: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False
    )


def _interfaces() -> str:
    psutil = _get_psutil()
    stats = psutil.net_if_stats()
    interfaces = []
    for name, addresses in psutil.net_if_addrs().items():
        item: dict[str, Any] = {"name": name, "addresses": []}
        stat = stats.get(name)
        if stat is not None:
            item["is_up"] = bool(getattr(stat, "isup", False))
        for address in addresses:
            item["addresses"].append(
                {
                    "family": str(getattr(address, "family", "")),
                    "address": str(getattr(address, "address", "")),
                    "netmask": getattr(address, "netmask", None),
                }
            )
        interfaces.append(item)
    return json.dumps(
        {"ok": True, "operation": "interfaces", "interfaces": interfaces},
        ensure_ascii=False,
    )


def _connection_records(args: dict[str, Any]) -> list[dict[str, Any]]:
    psutil = _get_psutil()
    status_filter = str(args.get("status", "")).upper()
    local_ip = str(args.get("local_ip", ""))
    remote_ip = str(args.get("remote_ip", ""))
    port = args.get("port")
    if port == 0:
        port = None
    include_process = bool(args.get("include_process", True))
    connections = []
    for conn in psutil.net_connections(kind="inet"):
        local = getattr(conn, "laddr", None)
        remote = getattr(conn, "raddr", None)
        local_address = str(getattr(local, "ip", "") or (local[0] if local else ""))
        local_port = int(getattr(local, "port", 0) or (local[1] if local else 0))
        remote_address = str(getattr(remote, "ip", "") or (remote[0] if remote else ""))
        remote_port = int(getattr(remote, "port", 0) or (remote[1] if remote else 0))
        status = str(getattr(conn, "status", ""))
        if status_filter and status != status_filter:
            continue
        if local_ip and local_address != local_ip:
            continue
        if remote_ip and remote_address != remote_ip:
            continue
        if port is not None and int(port) not in {local_port, remote_port}:
            continue
        item: dict[str, Any] = {
            "family": str(getattr(conn, "family", "")),
            "type": str(getattr(conn, "type", "")),
            "local_ip": local_address,
            "local_port": local_port,
            "remote_ip": remote_address,
            "remote_port": remote_port,
            "status": status,
        }
        if include_process:
            pid = getattr(conn, "pid", None)
            item["pid"] = pid
            if pid:
                try:
                    item["process_name"] = psutil.Process(pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    item["process_name"] = None
        connections.append(item)
    return connections


def _connections(args: dict[str, Any]) -> str:
    connections = _connection_records(args)
    return json.dumps(
        {"ok": True, "operation": "connections", "connections": connections},
        ensure_ascii=False,
    )


def _correlate(args: dict[str, Any]) -> str:
    findings = args.get("findings") or []
    if isinstance(findings, str):
        try:
            findings = json.loads(findings)
        except json.JSONDecodeError:
            return _error("INVALID_FINDINGS", "findings must be a JSON array.")
    if not isinstance(findings, list):
        return _error("INVALID_FINDINGS", "findings must be an array.")
    connections = _connection_records(args)
    results = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        src = str(finding.get("src") or "")
        dst = str(finding.get("dst") or "")
        dst_port = finding.get("dst_port")
        matches = [
            conn
            for conn in connections
            if src == conn.get("local_ip")
            and dst == conn.get("remote_ip")
            and (dst_port is None or int(dst_port) == conn.get("remote_port"))
        ]
        results.append(
            {"finding": finding, "matched": bool(matches), "connections": matches}
        )
    return json.dumps(
        {"ok": True, "operation": "correlate", "results": results},
        ensure_ascii=False,
    )


def _legacy_connections_removed(args: dict[str, Any]) -> str:
    # Kept out of the public API; the implementation is _connection_records.
    return _connections(args)


def run_tool(args: dict[str, Any]) -> str:
    operation = str(args.get("operation", "interfaces")).lower()
    try:
        if operation == "interfaces":
            return _interfaces()
        if operation == "connections":
            return _connections(args)
        if operation == "correlate":
            return _correlate(args)
        return _error(
            "UNSUPPORTED_OPERATION",
            "Supported operations are interfaces, connections, and correlate.",
        )
    except Exception as exc:
        return _error("LOCAL_NETWORK_FAILED", str(exc))


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "local_network",
        "description": _(
            "tool.description",
            default="Read local network interfaces and addresses.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["interfaces", "connections", "correlate"],
                    "default": "interfaces",
                    "description": _(
                        "param.operation.description", default="Discovery operation."
                    ),
                },
                "findings": {
                    "type": "array",
                    "description": _(
                        "param.findings.description",
                        default="Metadata-only pcap findings to correlate with current local connections.",
                    ),
                },
                "status": {
                    "type": "string",
                    "description": _(
                        "param.status.description",
                        default="Optional connection status filter, for example ESTABLISHED.",
                    ),
                },
                "local_ip": {
                    "type": "string",
                    "description": _(
                        "param.local_ip.description",
                        default="Optional local IP filter.",
                    ),
                },
                "remote_ip": {
                    "type": "string",
                    "description": _(
                        "param.remote_ip.description",
                        default="Optional remote IP filter.",
                    ),
                },
                "port": {
                    "type": "integer",
                    "minimum": 0,
                    "description": _(
                        "param.port.description",
                        default="Optional local or remote port filter.",
                    ),
                },
                "include_process": {
                    "type": "boolean",
                    "default": True,
                    "description": _(
                        "param.include_process.description",
                        default="Include PID and process name when permitted.",
                    ),
                },
            },
        },
    },
}
