"""Low-dependency protocol field inspection for local pcap files."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

from .i18n_helper import make_tool_translator
from .pcap_analyze_tool import _close_reader, _iter_packets, _packet_info

_ = make_tool_translator(__file__)
_SAFE_FIELDS = {
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "length",
    "tcp_flags",
    "tcp_seq",
    "tcp_payload_length",
    "dns_rcode",
    "dns_query_length",
}


def _find_tshark() -> str | None:
    explicit = os.environ.get("UAGENT_TSHARK_PATH", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    path = which("tshark")
    if path:
        return path
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
        ]
    else:
        candidates = ["/usr/bin/tshark", "/usr/local/bin/tshark", "/opt/homebrew/bin/tshark"]
    return next((candidate for candidate in candidates if os.path.isfile(candidate)), None)


def _run_tshark(path: str, display_filter: str, fields: list[str], limit: int) -> list[dict[str, Any]]:
    if any(any(char in field for char in "\r\n\t ;|") for field in fields):
        raise ValueError("invalid tshark field")
    tshark_path = _find_tshark()
    if not tshark_path:
        raise FileNotFoundError("tshark executable was not found")
    argv = [tshark_path, "-r", path, "-Y", display_filter, "-T", "fields", "-E", "separator=	"]
    for field in fields:
        argv.extend(["-e", field])
    result = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tshark failed")
    rows = []
    for line in result.stdout.splitlines()[:limit]:
        values = line.split("	")
        rows.append({field: (values[index] if index < len(values) else None) for index, field in enumerate(fields)})
    return rows


def _error(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False)


def run_tool(args: dict[str, Any]) -> str:
    source_text = str(args.get("pcap_path", "")).strip()
    if not source_text:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    backend = str(args.get("backend", "scapy")).lower()
    display_filter = str(args.get("display_filter", "")).strip()
    raw_fields = args.get("fields") or ["timestamp", "src_ip", "dst_ip", "protocol", "length"]
    if not isinstance(raw_fields, list):
        return _error("INVALID_FIELDS", "fields must be a list.")
    fields = [str(field) for field in raw_fields]
    forbidden = [field for field in fields if field not in _SAFE_FIELDS]
    if forbidden and not (backend in {"auto", "tshark"} and display_filter):
        return _error("FIELD_NOT_ALLOWED", f"Field is not allowed: {forbidden[0]}")
    source = Path(source_text).expanduser()
    if not source.is_file():
        return _error("INPUT_NOT_FOUND", "The input pcap file was not found.")
    limit = max(1, min(int(args.get("limit", 100)), 10000))
    if backend in {"auto", "tshark"} and display_filter:
        tshark_path = _find_tshark()
        if tshark_path:
            try:
                rows = _run_tshark(str(source), display_filter, fields, limit)
                return json.dumps({"ok": True, "backend": "tshark", "packets": rows, "returned_packets": len(rows), "truncated": len(rows) >= limit}, ensure_ascii=False)
            except Exception as exc:
                if backend == "tshark":
                    return _error("TSHARK_FAILED", str(exc))
        elif backend == "tshark":
            return _error("EXTERNAL_DEPENDENCY_MISSING", "tshark executable was not found.")
        degraded = True
    else:
        degraded = False
    if forbidden:
        fields = [field for field in fields if field in _SAFE_FIELDS]

    selected: list[dict[str, Any]] = []
    truncated = False
    reader = _iter_packets(str(source))
    try:
        for packet in reader:
            if len(selected) >= limit:
                truncated = True
                break
            info = _packet_info(packet)
            selected.append({field: info.get(field) for field in fields})
    finally:
        _close_reader(reader)

    return json.dumps(
        {
            "ok": True,
            "backend": "scapy",
            "degraded": degraded,
            "packets": selected,
            "returned_packets": len(selected),
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "protocol_inspect",
        "description": _(
            "tool.description",
            default="Inspect selected protocol fields from a local pcap without returning payloads.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pcap_path": {"type": "string"},
                "backend": {"type": "string", "enum": ["scapy", "auto", "tshark"], "default": "scapy"},
                "display_filter": {"type": "string", "description": "Optional tshark display filter."},
                "fields": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 100},
            },
            "required": ["pcap_path"],
        },
    },
}
