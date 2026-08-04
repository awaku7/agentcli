"""Preflight network dependencies and privilege state without running scans."""
from __future__ import annotations

import importlib.util
import json
import os
import platform
from shutil import which
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _python_is_admin() -> bool:
    if os.name == "nt":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _executable_status(name: str) -> dict[str, Any]:
    path = which(name)
    return {"status": "available" if path else "missing", "path": path}


def _npcap_status() -> dict[str, Any]:
    if os.name != "nt":
        return {"status": "not_applicable", "path": None}
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = [
        os.path.join(windir, "System32", "Npcap", "wpcap.dll"),
        os.path.join(windir, "System32", "wpcap.dll"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return {"status": "available", "path": candidate}
    return {"status": "missing", "path": None}


def run_tool(args: dict[str, Any]) -> str:
    del args
    packages = {}
    for package in ("scapy", "psutil", "httpx", "dnspython", "pyroute2"):
        import_name = "dns" if package == "dnspython" else package
        packages[package] = {
            "status": "available" if importlib.util.find_spec(import_name) else "missing",
            "import_name": import_name,
        }
    executables = {name: _executable_status(name) for name in ("nmap", "tshark", "wireshark", "zeek", "suricata")}
    elevated = _python_is_admin()
    return json.dumps(
        {
            "ok": True,
            "platform": platform.system().lower(),
            "python": platform.python_version(),
            "packages": packages,
            "executables": executables,
            "drivers": {"npcap": _npcap_status()},
            "privilege": {
                "elevated": elevated,
                "raw_packet_possible": elevated,
                "uac_available": os.name == "nt" and not elevated,
            },
        },
        ensure_ascii=False,
    )


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "network_capabilities",
        "description": _(
            "tool.description",
            default="Check network tool dependencies, external commands, and privilege state.",
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}
