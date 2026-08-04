"""Offline PCAP analysis orchestration tool.

This is intentionally an offline integration step: it composes the existing
``pcap_analyze`` and ``local_network`` tools without opening sockets or
starting a live capture. Live capture can be added later behind an explicit
permission boundary.
"""
from __future__ import annotations

import json
from typing import Any

from . import local_network_tool, pcap_analyze_tool
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

_DEFAULT_OPERATIONS = ("summary", "flows", "detect", "impact")
_ALLOWED_OPERATIONS = {"summary", "statistics", "flows", "detect", "impact"}


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
    """Run offline analysis and optionally correlate flows with local sockets."""
    pcap_path = str(args.get("pcap_path", "")).strip()
    if not pcap_path:
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "INPUT_REQUIRED",
                    "message": "pcap_path is required.",
                },
            },
            ensure_ascii=False,
        )

    raw_operations = args.get("operations", list(_DEFAULT_OPERATIONS))
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
            pcap_analyze_tool.run_tool(_analysis_args(args, operation))
        )
        results[operation] = result
        if result.get("ok") is False:
            errors.append({"operation": operation, "error": result.get("error")})

    correlation: dict[str, Any] | None = None
    if bool(args.get("correlate", True)) and "flows" in results and results["flows"].get("ok"):
        local_args = {
            "operation": "correlate",
            "findings": _flow_findings(results["flows"]),
            "status": args.get("status", ""),
            "local_ip": args.get("local_ip", ""),
            "remote_ip": args.get("remote_ip", ""),
            "port": args.get("port", 0),
            "include_process": args.get("include_process", True),
        }
        correlation = _json_result(local_network_tool.run_tool(local_args))
        if correlation.get("ok") is False:
            errors.append({"operation": "correlate", "error": correlation.get("error")})

    return json.dumps(
        {
            "ok": not errors,
            "operation": "capture_analyze",
            "pcap_path": pcap_path,
            "analysis": results,
            "classification": _classify(results, errors),
            "correlation": correlation,
            "warnings": [
                "This operation analyzes an existing pcap; it does not start live capture."
            ],
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
                "pcap_path": {"type": "string", "description": "Input pcap path."},
                "operations": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(_ALLOWED_OPERATIONS)},
                    "default": list(_DEFAULT_OPERATIONS),
                    "description": "Analysis operations: summary, statistics, flows, detect, impact.",
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
            "required": ["pcap_path"],
        },
    },
}
