"""Low-privilege network probes."""
from __future__ import annotations

import json
import os
import socket
import time
from typing import Any

from . import network_privileged_helper, windows_uac_launcher

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _probe_tcp(target: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with socket.create_connection((target, port), timeout=timeout):
            state = "open"
    except (ConnectionRefusedError, TimeoutError, socket.timeout):
        state = "closed"
    except OSError as exc:
        return {"state": "unreachable", "error": str(exc)}
    return {"state": state, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}


def _error(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False)


def _run_elevated_raw(action: str, target: str, port: int) -> str:
    request = {"action": action, "target": target, "port": port, "dry_run": False}
    if os.name != "nt":
        try:
            is_root = os.geteuid() == 0
        except AttributeError:
            is_root = False
        if not is_root:
            return _error(
                "PRIVILEGE_REQUIRED",
                "Run uag as root or configure a restricted helper with CAP_NET_RAW.",
            )
        try:
            result = network_privileged_helper.run_request(request)
        except Exception as exc:
            return _error("PRIVILEGED_HELPER_FAILED", str(exc))
        result["elevated"] = True
        return json.dumps(result, ensure_ascii=False)

    request_path, result_path = windows_uac_launcher.create_request_paths()
    windows_uac_launcher.write_request(
        request_path,
        {"action": action, "target": target, "port": port, "dry_run": False},
    )
    command = windows_uac_launcher.build_helper_command(str(request_path), str(result_path))
    try:
        windows_uac_launcher.shell_execute_runas(command)
        result = windows_uac_launcher.wait_for_result(result_path, timeout=30)
    except PermissionError:
        return _error("ELEVATION_CANCELLED", "The Windows UAC request was cancelled.")
    except TimeoutError:
        return _error("ELEVATION_TIMEOUT", "The privileged helper did not return in time.")
    except Exception as exc:
        return _error("ELEVATION_FAILED", str(exc))
    result["elevated"] = True
    return json.dumps(result, ensure_ascii=False)


def run_tool(args: dict[str, Any]) -> str:
    action = str(args.get("action", "tcp_connect")).lower()
    target = str(args.get("target", "")).strip()
    if not target:
        return _error("TARGET_REQUIRED", "target is required.")
    try:
        port = int(args.get("port", 0))
    except (TypeError, ValueError):
        return _error("INVALID_PORT", "port must be an integer.")
    if port < 1 or port > 65535:
        return _error("INVALID_PORT", "port must be between 1 and 65535.")
    timeout = max(0.1, min(float(args.get("timeout", 2)), 30.0))

    if action in {"tcp_syn", "icmp", "arp"}:
        dry_run = bool(args.get("dry_run", False))
        if bool(args.get("allow_elevation", False)) and not dry_run:
            if not bool(args.get("elevation_confirmed", False)):
                return _error(
                    "ELEVATION_CONFIRMATION_REQUIRED",
                    "Call human_ask and retry with elevation_confirmed=true.",
                )
            return _run_elevated_raw(action, target, port)
        if dry_run:
            return json.dumps(
                {
                    "ok": True,
                    "backend": "scapy",
                    "action": action,
                    "target": target,
                    "port": port,
                    "dry_run": True,
                    "requires_privilege": True,
                },
                ensure_ascii=False,
            )
        return _error(
            "PRIVILEGE_REQUIRED",
            f"{action} requires a privileged packet backend and is not enabled yet.",
        )
    if action != "tcp_connect":
        return _error("UNSUPPORTED_ACTION", "Only tcp_connect is implemented.")

    result = _probe_tcp(target, port, timeout)
    return json.dumps(
        {
            "ok": True,
            "backend": "socket",
            "action": action,
            "target": target,
            "port": port,
            **result,
        },
        ensure_ascii=False,
    )


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "packet_probe",
        "description": _(
            "tool.description",
            default="Probe a network target using a low-privilege Python socket backend.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["tcp_connect", "tcp_syn", "icmp", "arp"]},
                "target": {"type": "string"},
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "timeout": {"type": "number", "minimum": 0.1, "maximum": 30, "default": 2},
                "dry_run": {"type": "boolean", "default": False},
                "allow_elevation": {"type": "boolean", "default": False},
                "elevation_confirmed": {"type": "boolean", "default": False},
            },
            "required": ["action", "target"],
        },
    },
}
