"""Low-privilege network discovery using Python's standard library."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import xml.etree.ElementTree as ET
from shutil import which
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)
_MAX_PORTS = 256


def _probe_tcp(target: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with socket.create_connection((target, port), timeout=timeout):
            state = "open"
    except (ConnectionRefusedError, TimeoutError, socket.timeout):
        state = "closed"
    except OSError as exc:
        state = "unreachable"
        error = str(exc)
    result: dict[str, Any] = {
        "port": port,
        "state": state,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    if state == "unreachable":
        result["error"] = error
    return result


def _find_nmap() -> str | None:
    explicit = os.environ.get("UAGENT_NMAP_PATH", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    path = which("nmap")
    if path:
        return path
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\Nmap\nmap.exe",
            r"C:\Program Files (x86)\Nmap\nmap.exe",
        ]
    else:
        candidates = ["/usr/bin/nmap", "/usr/local/bin/nmap", "/snap/bin/nmap", "/opt/homebrew/bin/nmap"]
    return next((candidate for candidate in candidates if os.path.isfile(candidate)), None)


def _run_nmap(mode: str, target: str, ports: list[int], timeout: float) -> str:
    nmap_path = _find_nmap()
    if nmap_path is None:
        raise FileNotFoundError("nmap executable was not found")
    argv = [nmap_path, "-oX", "-", "-T2"]
    if mode == "host_discovery":
        argv.append("-sn")
    elif mode == "service_scan":
        argv.append("-sV")
    elif mode == "os_scan":
        argv.append("-O")
    else:
        raise ValueError("unsupported nmap mode")
    if ports and mode != "host_discovery":
        argv.extend(["-p", ",".join(str(port) for port in ports)])
    argv.append(target)
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"nmap exited with {result.returncode}")
    return result.stdout


def _parse_nmap_xml(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    hosts = []
    for host in root.findall("host"):
        address = host.find("address")
        item: dict[str, Any] = {
            "ip": address.attrib.get("addr") if address is not None else None,
            "status": (host.find("status").attrib.get("state") if host.find("status") is not None else "unknown"),
            "ports": [],
        }
        for port in host.findall("./ports/port"):
            state = port.find("state")
            service = port.find("service")
            entry: dict[str, Any] = {
                "port": int(port.attrib.get("portid", 0)),
                "protocol": port.attrib.get("protocol"),
                "state": state.attrib.get("state") if state is not None else "unknown",
            }
            if service is not None:
                entry["service"] = service.attrib.get("name")
                product = service.attrib.get("product")
                version = service.attrib.get("version")
                if product or version:
                    entry["version"] = " ".join(part for part in (product, version) if part)
            item["ports"].append(entry)
        hosts.append(item)
    return hosts


def _error(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False)


def _port_scan(args: dict[str, Any]) -> str:
    target = str(args.get("target", "")).strip()
    if not target:
        return _error("TARGET_REQUIRED", "target is required.")
    raw_ports = args.get("ports")
    if not isinstance(raw_ports, list) or not raw_ports:
        return _error("PORTS_REQUIRED", "ports must be a non-empty list.")
    if len(raw_ports) > _MAX_PORTS:
        return _error("PORT_LIMIT_EXCEEDED", f"At most {_MAX_PORTS} ports may be scanned per call.")
    try:
        ports = sorted({int(port) for port in raw_ports})
    except (TypeError, ValueError):
        return _error("INVALID_PORT", "ports must contain integers.")
    if any(port < 1 or port > 65535 for port in ports):
        return _error("INVALID_PORT", "ports must be between 1 and 65535.")
    timeout = max(0.1, min(float(args.get("timeout", 2)), 30.0))
    results = [_probe_tcp(target, port, timeout) for port in ports]
    return json.dumps(
        {
            "ok": True,
            "backend": "socket",
            "target": target,
            "results": results,
            "open_ports": [item["port"] for item in results if item["state"] == "open"],
        },
        ensure_ascii=False,
    )


def run_tool(args: dict[str, Any]) -> str:
    mode = str(args.get("mode", "port_scan")).lower()
    try:
        if mode == "port_scan":
            return _port_scan(args)
        if mode in {"host_discovery", "service_scan", "os_scan"}:
            target = str(args.get("target", "")).strip()
            if not target:
                return _error("TARGET_REQUIRED", "target is required.")
            raw_ports = args.get("ports") or []
            ports = [int(port) for port in raw_ports]
            timeout = max(1.0, min(float(args.get("timeout", 30)), 300.0))
            try:
                xml_text = _run_nmap(mode, target, ports, timeout)
            except FileNotFoundError:
                return _error("EXTERNAL_DEPENDENCY_MISSING", "nmap executable was not found.")
            hosts = _parse_nmap_xml(xml_text)
            return json.dumps({"ok": True, "backend": "nmap", "mode": mode, "hosts": hosts}, ensure_ascii=False)
        return _error("UNSUPPORTED_MODE", "Unsupported discovery mode.")
    except Exception as exc:
        return _error("NETWORK_DISCOVER_FAILED", str(exc))


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "network_discover",
        "description": _(
            "tool.description",
            default="Discover TCP ports using a low-privilege Python socket backend.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["port_scan", "host_discovery", "service_scan", "os_scan"], "default": "port_scan"},
                "target": {"type": "string", "description": _("param.target.description", default="Single host or IP address.")},
                "ports": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 65535}},
                "timeout": {"type": "number", "minimum": 0.1, "maximum": 30, "default": 2},
            },
            "required": ["target", "ports"],
        },
    },
}
