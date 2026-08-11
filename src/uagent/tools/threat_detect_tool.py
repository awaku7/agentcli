"""Suricata EVE alert extraction with metadata-only output."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _find_suricata() -> str | None:
    explicit = os.environ.get("UAGENT_SURICATA_PATH", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    return which("suricata")


def _run_suricata(pcap_path: str, output_dir: str) -> Path:
    suricata = _find_suricata()
    if not suricata:
        raise FileNotFoundError("suricata executable was not found")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [suricata, "-r", pcap_path, "-l", str(out)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "suricata failed")
    return out / "eve.json"


def _parse_eve(path: Path, limit: int) -> list[dict[str, Any]]:
    alerts = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "alert":
            continue
        alert = event.get("alert") or {}
        alerts.append(
            {
                "timestamp": event.get("timestamp"),
                "src_ip": event.get("src_ip"),
                "src_port": event.get("src_port"),
                "dest_ip": event.get("dest_ip"),
                "dest_port": event.get("dest_port"),
                "signature": alert.get("signature"),
                "category": alert.get("category"),
                "severity": alert.get("severity"),
                "action": alert.get("action"),
            }
        )
        if len(alerts) >= limit:
            break
    return alerts


def _error(code: str, message: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": message}}, ensure_ascii=False
    )


def run_tool(args: dict[str, Any]) -> str:
    pcap_path = str(args.get("pcap_path", "")).strip()
    if not pcap_path:
        return _error("INPUT_REQUIRED", "pcap_path is required.")
    limit = max(1, min(int(args.get("limit", 100)), 10000))
    try:
        if _find_suricata() is None:
            return _error(
                "EXTERNAL_DEPENDENCY_MISSING", "suricata executable was not found."
            )
        eve_path = _run_suricata(
            pcap_path, str(args.get("output_dir", "outputs/suricata"))
        )
        alerts = _parse_eve(eve_path, limit)
        return json.dumps(
            {
                "ok": True,
                "backend": "suricata",
                "alerts": alerts,
                "returned_alerts": len(alerts),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error("SURICATA_FAILED", str(exc))


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "threat_detect",
        "description": _(
            "tool.description",
            default="Extract Suricata IDS alerts from a pcap as metadata.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pcap_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "outputs/suricata"},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "default": 100,
                },
            },
            "required": ["pcap_path"],
        },
    },
}
