"""Zeek-backed traffic log extraction with metadata-only output."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _find_zeek() -> str | None:
    explicit = os.environ.get("UAGENT_ZEEK_PATH", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit
    return which("zeek")


def _run_zeek(pcap_path: str, output_dir: str) -> Path:
    zeek = _find_zeek()
    if not zeek:
        raise FileNotFoundError("zeek executable was not found")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [zeek, "-r", pcap_path],
        cwd=out,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "zeek failed")
    return out / "conn.log"


def _parse_conn_log(path: Path, limit: int) -> list[dict[str, Any]]:
    fields: list[str] | None = None
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#fields"):
            normalized = line.replace(chr(92) + "x09", chr(9))
            fields = normalized[len("#fields") :].lstrip(" 	").split(chr(9))
            continue
        if not line or line.startswith("#") or fields is None:
            continue
        values = line.split("\t")
        events.append(
            {
                field: values[index] if index < len(values) else None
                for index, field in enumerate(fields)
            }
        )
        if len(events) >= limit:
            break
    return events


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
        if _find_zeek() is None:
            return _error(
                "EXTERNAL_DEPENDENCY_MISSING", "zeek executable was not found."
            )
        log_path = _run_zeek(pcap_path, str(args.get("output_dir", "outputs/zeek")))
        events = _parse_conn_log(log_path, limit)
        return json.dumps(
            {
                "ok": True,
                "backend": "zeek",
                "events": events,
                "returned_events": len(events),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return _error("ZEEK_FAILED", str(exc))


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "x_parallel_safe": False,
    "function": {
        "name": "traffic_monitor",
        "description": _(
            "tool.description",
            default="Extract metadata-only traffic events from a pcap using Zeek.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pcap_path": {"type": "string"},
                "output_dir": {"type": "string", "default": "outputs/zeek"},
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
