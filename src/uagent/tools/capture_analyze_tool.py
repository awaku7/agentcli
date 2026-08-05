"""Offline PCAP analysis orchestration tool.

This is intentionally an offline integration step: it composes the existing
``pcap_analyze`` and ``local_network`` tools without opening sockets or
starting a live capture. Live capture can be added later behind an explicit
permission boundary.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from . import local_network_tool, pcap_analyze_tool
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_DEFAULT_OPERATIONS = ("summary", "flows", "detect", "impact")
_ALLOWED_OPERATIONS = {"summary", "statistics", "flows", "detect", "impact"}
_LOOPBACK_ALIASES = {"loopback", "lo", "lo0", "loopback0"}


def _resolve_loopback_interface(requested: str) -> str | None:
    value = str(requested or "loopback").strip()
    if value.lower() in _LOOPBACK_ALIASES:
        try:
            from scapy.all import conf

            configured = str(getattr(conf, "loopback_name", "") or "")
            interfaces = getattr(conf, "ifaces", {})
            for iface in getattr(interfaces, "values", lambda: [])():
                name = str(getattr(iface, "name", "") or "")
                ip = str(getattr(iface, "ip", "") or "")
                if configured == name or ip == "127.0.0.1" or "loopback" in name.lower():
                    return name or configured or None
            return configured or None
        except Exception:
            return None
    if "loopback" in value.lower():
        return value
    return None


def _capture_loopback(args: dict[str, Any]) -> dict[str, Any]:
    """Capture only on a loopback interface and save a local pcap artifact."""
    interface = str(args.get("interface", "loopback") or "loopback").strip()
    resolved = _resolve_loopback_interface(interface)
    if not resolved:
        return {
            "ok": False,
            "error": {
                "code": "INTERFACE_NOT_ALLOWED",
                "message": "Live capture is restricted to a loopback interface.",
                "interface": interface,
            },
        }

    duration = max(1, min(int(args.get("duration", 10) or 10), 60))
    max_packets = max(1, min(int(args.get("max_packets", 1000) or 1000), 10000))
    bpf_filter = str(args.get("bpf_filter", "") or "").strip()
    try:
        try:
            from scapy.all import sniff
            from scapy.utils import wrpcap
        except ImportError:
            from .._pip_auto import install_with_status

            if not install_with_status("scapy", "scapy", version_spec=">=2.6.0"):
                raise RuntimeError("scapy is unavailable")
            from scapy.all import sniff
            from scapy.utils import wrpcap

        sniff_args: dict[str, Any] = {
            "iface": resolved,
            "timeout": duration,
            "count": max_packets,
            "store": True,
        }
        if bpf_filter:
            sniff_args["filter"] = bpf_filter
        packets = sniff(**sniff_args)

        fd, path = tempfile.mkstemp(prefix="capture_analyze_", suffix=".pcap")
        os.close(fd)
        wrpcap(path, packets)
        return {
            "ok": True,
            "interface": resolved,
            "duration": duration,
            "max_packets": max_packets,
            "packet_count": len(packets),
            "pcap_path": str(Path(path)),
        }
    except PermissionError as exc:
        return {"ok": False, "error": {"code": "PRIVILEGE_REQUIRED", "message": str(exc)}}
    except Exception as exc:
        message = str(exc)
        code = "EXTERNAL_DEPENDENCY_MISSING" if "pcap" in message.lower() or "libpcap" in message.lower() else "LIVE_CAPTURE_FAILED"
        return {"ok": False, "error": {"code": code, "message": message}}


def _json_result(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {
            "ok": False,
            "error": {
                "code": "INVALID_SUBTOOL_RESPONSE",
                "message": "A composed tool returned invalid JSON.",
            },
        }
    return parsed if isinstance(parsed, dict) else {"ok": True, "data": parsed}


def _flow_findings(flow_result: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for flow in flow_result.get("flows", []) or []:
        if not isinstance(flow, dict):
            continue
        src = flow.get("src_ip")
        dst = flow.get("dst_ip")
        if not src or not dst:
            continue
        findings.append(
            {
                "src": src,
                "dst": dst,
                "src_port": flow.get("src_port"),
                "dst_port": flow.get("dst_port"),
                "protocol": flow.get("protocol"),
                "packets": flow.get("packets", 0),
                "bytes": flow.get("bytes", 0),
            }
        )
    return findings


def _classify(results: dict[str, dict[str, Any]], errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify evidence conservatively; never treat this as an attack verdict."""
    if errors:
        return {"classification": "unknown", "score": None, "reasons": ["analysis_error"]}

    detect = results.get("detect", {})
    findings = detect.get("findings", []) or []
    categories = {
        str(item.get("category", ""))
        for item in findings
        if isinstance(item, dict)
    }
    high = sum(1 for item in findings if isinstance(item, dict) and item.get("severity") == "high")
    medium = sum(1 for item in findings if isinstance(item, dict) and item.get("severity") == "medium")
    low = sum(1 for item in findings if isinstance(item, dict) and item.get("severity") == "low")
    reasons = sorted(category for category in categories if category)
    strong = {"port_scan", "host_scan", "beaconing", "syn_flood_candidate"}
    if high > 0 or len(categories & strong) >= 2 or medium >= 2:
        return {"classification": "suspicious", "score": 80, "reasons": reasons}

    impact_scores = [
        float(item.get("impact_score", 0) or 0)
        for item in (results.get("impact", {}).get("devices", []) or [])
        if isinstance(item, dict)
    ]
    max_impact = max(impact_scores, default=0.0)
    if medium > 0 or low > 0 or max_impact >= 40:
        if max_impact >= 60:
            reasons.append("impact_score")
        return {"classification": "review", "score": round(max(max_impact, 40), 2), "reasons": reasons}
    if "detect" in results:
        return {"classification": "normal", "score": round(max_impact, 2), "reasons": []}
    return {"classification": "unknown", "score": None, "reasons": ["insufficient_evidence"]}


def _analysis_args(args: dict[str, Any], operation: str) -> dict[str, Any]:
    forwarded = {
        "pcap_path": args.get("pcap_path", ""),
        "operation": operation,
        "detail_level": args.get("detail_level", 1),
        "rules": args.get("rules"),
        "thresholds": args.get("thresholds"),
        "filter": args.get("filter"),
        "limit": args.get("limit", 1000),
        "output_path": args.get("output_path", ""),
        "overwrite": args.get("overwrite", False),
    }
    return {key: value for key, value in forwarded.items() if value is not None}


def run_tool(args: dict[str, Any]) -> str:
    """Run offline analysis or a bounded loopback capture followed by analysis."""
    work_args = dict(args)
    capture_info: dict[str, Any] | None = None
    if bool(work_args.get("live_capture", False)):
        capture_info = _capture_loopback(work_args)
        if not capture_info.get("ok"):
            return json.dumps(capture_info, ensure_ascii=False)
        work_args["pcap_path"] = capture_info["pcap_path"]

    pcap_path = str(work_args.get("pcap_path", "")).strip()
    if not pcap_path:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "INPUT_REQUIRED",
                    "message": "pcap_path is required unless live_capture is true.",
                },
            },
            ensure_ascii=False,
        )

    raw_operations = work_args.get("operations", list(_DEFAULT_OPERATIONS))
    if isinstance(raw_operations, str):
        operations = [item.strip().lower() for item in raw_operations.split(",") if item.strip()]
    elif isinstance(raw_operations, list):
        operations = [str(item).strip().lower() for item in raw_operations if str(item).strip()]
    else:
        operations = list(_DEFAULT_OPERATIONS)

    allowed = _ALLOWED_OPERATIONS
    invalid = [item for item in operations if item not in allowed]
    if invalid:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "UNSUPPORTED_OPERATION",
                    "message": "Unsupported capture_analyze operation.",
                    "details": {"operations": invalid, "allowed": sorted(allowed)},
                },
            },
            ensure_ascii=False,
        )

    results: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    for operation in dict.fromkeys(operations):
        result = _json_result(
            pcap_analyze_tool.run_tool(_analysis_args(work_args, operation))
        )
        results[operation] = result
        if result.get("ok") is False:
            errors.append({"operation": operation, "error": result.get("error")})

    correlation: dict[str, Any] | None = None
    if bool(work_args.get("correlate", True)) and "flows" in results and results["flows"].get("ok"):
        local_args = {
            "operation": "correlate",
            "findings": _flow_findings(results["flows"]),
            "status": work_args.get("status", ""),
            "local_ip": work_args.get("local_ip", ""),
            "remote_ip": work_args.get("remote_ip", ""),
            "port": work_args.get("port", 0),
            "include_process": work_args.get("include_process", True),
        }
        correlation = _json_result(local_network_tool.run_tool(local_args))
        if correlation.get("ok") is False:
            errors.append({"operation": "correlate", "error": correlation.get("error")})

    return json.dumps(
        {
            "ok": not errors,
            "operation": "capture_analyze",
            "pcap_path": pcap_path,
            "capture": capture_info,
            "analysis": results,
            "classification": _classify(results, errors),
            "correlation": correlation,
            "warnings": (
                ["Live capture is restricted to a loopback interface."]
                if capture_info is not None
                else ["This operation analyzes an existing pcap; it does not start live capture."]
            ),
            "errors": errors,
        },
        ensure_ascii=False,
    )


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "capture_analyze",
        "description": _(
            "tool.description",
            default="Run offline pcap analysis and correlate flows with local connections.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pcap_path": {"type": "string", "description": _("param.pcap_path.description", default="Input pcap path; omit when live_capture is true.")},
                "live_capture": {"type": "boolean", "default": False, "description": _("param.live_capture.description", default="Capture only on a loopback interface before analyzing.")},
                "interface": {"type": "string", "default": "loopback", "description": _("param.interface.description", default="Loopback interface alias or name; non-loopback interfaces are rejected.")},
                "duration": {"type": "integer", "minimum": 1, "maximum": 60, "default": 10, "description": _("param.duration.description", default="Live capture duration in seconds.")},
                "max_packets": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 1000, "description": _("param.max_packets.description", default="Maximum packets captured.")},
                "bpf_filter": {"type": "string", "description": _("param.bpf_filter.description", default="Optional BPF capture filter.")},
                "operations": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(_ALLOWED_OPERATIONS)},
                    "default": list(_DEFAULT_OPERATIONS),
                    "description": _("param.operations.description", default="Analysis operations: summary, statistics, flows, detect, impact."),
                },
                "correlate": {"type": "boolean", "default": True},
                "detail_level": {"type": "integer", "minimum": 0, "maximum": 2, "default": 1},
                "rules": {"type": "array", "items": {"type": "string"}},
                "thresholds": {"type": "object"},
                "filter": {"type": "object"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1000},
                "status": {"type": "string"},
                "local_ip": {"type": "string"},
                "remote_ip": {"type": "string"},
                "port": {"type": "integer", "minimum": 0},
                "include_process": {"type": "boolean", "default": True},
            },
            "required": [],
        },
    },
}
