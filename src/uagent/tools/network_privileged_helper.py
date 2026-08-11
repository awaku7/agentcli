"""Restricted helper boundary for future Windows UAC packet probes.

This module intentionally accepts structured probe requests only. It is not a
TOOL_SPEC and must not be exposed as an arbitrary command runner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_ALLOWED_ACTIONS = {"tcp_syn", "icmp", "arp"}


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError(_("error.request_object", default="request must be an object"))
    action = request.get("action")
    if action not in _ALLOWED_ACTIONS:
        raise ValueError(_("error.action_not_allowed", default="action is not allowed"))
    target = str(request.get("target", "")).strip()
    if not target:
        raise ValueError(_("error.target_required", default="target is required"))
    try:
        port = int(request.get("port", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            _("error.port_integer", default="port must be an integer")
        ) from exc
    if action == "tcp_syn" and not 1 <= port <= 65535:
        raise ValueError(
            _(
                "error.port_range",
                default="port must be between 1 and 65535 for tcp_syn",
            )
        )
    if action != "tcp_syn":
        port = 0
    return {
        "action": action,
        "target": target,
        "port": port,
        "dry_run": bool(request.get("dry_run", True)),
    }


def _scapy_probe(request: dict[str, Any]) -> dict[str, Any]:
    from .._pip_auto import install_with_status

    try:
        from scapy.all import ARP, ICMP, IP, TCP, Ether, conf, sr1, srp
    except ImportError:
        if not install_with_status("scapy", "scapy", version_spec=">=2.6.0"):
            raise RuntimeError(
                _("error.scapy_unavailable", default="scapy is unavailable")
            )
        from scapy.all import ARP, ICMP, IP, TCP, Ether, conf, sr1, srp

    action = request["action"]
    target = request["target"]
    if action == "tcp_syn":
        reply = sr1(
            IP(dst=target) / TCP(dport=request["port"], flags="S"),
            timeout=2,
            verbose=False,
        )
        if reply is None:
            state = "no_response"
        elif reply.haslayer(TCP) and reply[TCP].flags & 0x12 == 0x12:
            state = "open"
        elif reply.haslayer(TCP) and reply[TCP].flags & 0x04:
            state = "closed"
        else:
            state = "other_response"
        return {
            "action": action,
            "target": target,
            "port": request["port"],
            "state": state,
        }
    if action == "icmp":
        reply = sr1(IP(dst=target) / ICMP(), timeout=2, verbose=False)
        return {
            "action": action,
            "target": target,
            "state": "reachable" if reply else "no_response",
        }
    conf.verb = 0
    answered, unused_answers = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target), timeout=2, verbose=False
    )
    return {
        "action": action,
        "target": target,
        "state": "reachable" if answered else "no_response",
    }


def run_request(request: dict[str, Any]) -> dict[str, Any]:
    validated = validate_request(request)
    if validated["dry_run"]:
        return {"ok": True, "dry_run": True, "plan": validated}
    return {"ok": True, "dry_run": False, "result": _scapy_probe(validated)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restricted network privileged helper")
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    result_path = Path(args.result)
    try:
        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        result = run_request(request)
    except Exception as exc:
        result = {"ok": False, "error": {"code": "HELPER_FAILED", "message": str(exc)}}
    temporary = result_path.with_suffix(result_path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(result_path)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
