from __future__ import annotations

import json
import time
from typing import Any

from .echonet_node_status_tool import (
    _merge_properties,
    _property_map,
    _query_node,
    _resolve_target_eoj,
    _now_iso,
    _normalize_int,
)
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:echonet_monitor"

_DEFAULT_INTERVAL = 5
_DEFAULT_DURATION = 30
_DEFAULT_TIMEOUT = 4

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "echonet_monitor",
        "description": _(
            "tool.description",
            default=(
                "Poll an ECHONET Lite node repeatedly, detect property changes, and return a JSON or text summary."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": _(
                        "param.ip.description",
                        default="Target node IPv4 address.",
                    ),
                },
                "eoj": {
                    "type": "string",
                    "description": _(
                        "param.eoj.description",
                        default=("Target EOJ (default: node profile)."),
                    ),
                },
                "obj": {
                    "type": "string",
                    "description": _(
                        "param.obj.description",
                        default=("Object code filter (e.g. '0130')."),
                    ),
                },
                "interval": {
                    "type": "integer",
                    "default": _DEFAULT_INTERVAL,
                    "minimum": 1,
                    "description": _(
                        "param.interval.description",
                        default="Polling interval in seconds.",
                    ),
                },
                "duration": {
                    "type": "integer",
                    "default": _DEFAULT_DURATION,
                    "minimum": 1,
                    "description": _(
                        "param.duration.description",
                        default="Monitoring duration in seconds.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": _DEFAULT_TIMEOUT,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="Timeout (seconds).",
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description",
                        default="Format: json or text.",
                    ),
                },
            },
            "required": ["ip_address"],
            "additionalProperties": False,
        },
    },
}


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
        return value
    except Exception:
        return str(value)


def _extract_properties(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged = _merge_properties(*(frame.get("properties") or [] for frame in frames))
    return _property_map(merged)


def _snapshot_from_frames(frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    props = _extract_properties(frames)
    snapshot: dict[str, dict[str, Any]] = {}
    for epc, prop in props.items():
        snapshot[epc] = {
            "epc": prop.get("epc"),
            "name": prop.get("name"),
            "value": _safe_json(prop.get("value")),
            "format": prop.get("format"),
            "raw_hex": prop.get("raw_hex"),
        }
    return snapshot


def _snapshot_changes(
    previous: dict[str, dict[str, Any]] | None,
    current: dict[str, dict[str, Any]],
    *,
    timestamp: str,
    ip_address: str,
    target_eoj: str,
    target_name: str | None,
) -> list[dict[str, Any]]:
    if previous is None:
        return []

    changes: list[dict[str, Any]] = []
    keys = sorted(set(previous) | set(current))
    for epc in keys:
        before = previous.get(epc)
        after = current.get(epc)
        before_key = (
            None
            if before is None
            else (before.get("raw_hex"), before.get("value"), before.get("format"))
        )
        after_key = (
            None
            if after is None
            else (after.get("raw_hex"), after.get("value"), after.get("format"))
        )
        if before_key == after_key:
            continue
        changes.append(
            {
                "timestamp": timestamp,
                "node": {
                    "ip": ip_address,
                    "node_id": ip_address,
                },
                "object": {
                    "eoj": target_eoj,
                    "class_name": target_name,
                },
                "property": after or before or {"epc": epc},
                "before": before.get("value") if before else None,
                "after": after.get("value") if after else None,
            }
        )
    return changes


def _format_text(payload: dict[str, Any]) -> str:
    lines = [
        _(
            "msg.summary",
            default="ECHONET Lite monitoring completed: {count} change(s) in {elapsed_ms} ms.",
            count=payload.get("count", 0),
            elapsed_ms=payload.get("elapsed_ms", 0),
        )
    ]
    target = payload.get("target") or {}
    if target.get("ip"):
        lines.append(f"IP: {target.get('ip_address')}")
    if target.get("eoj"):
        lines.append(f"EOJ: {target.get('eoj')}")
    if target.get("obj"):
        lines.append(f"object_code: {target.get('object_code')}")
    lines.append(f"Interval: {payload.get('interval')} s")
    lines.append(f"Duration: {payload.get('duration')} s")
    lines.append(f"Timeout: {payload.get('timeout')} s")
    lines.append(f"Polls: {payload.get('polls')}")
    lines.append(f"Stopped: {payload.get('stopped_reason')}")
    lines.append("")

    changes = payload.get("changes") or []
    if not changes:
        lines.append(
            _(
                "msg.no_changes",
                default="No property changes were detected.",
            )
        )
        return "\n".join(lines).strip()

    for idx, change in enumerate(changes, 1):
        prop = change.get("property") or {}
        lines.append(f"[{idx}] {change.get('timestamp')}")
        lines.append(f"  property: {prop.get('epc')} {prop.get('name')}")
        lines.append(f"  before: {change.get('before')}")
        lines.append(f"  after: {change.get('after')}")
        lines.append("")
    return "\n".join(lines).strip()


def run_tool(args: dict[str, Any]) -> str:
    ip_address = str(args.get("ip") or "").strip()
    eoj_arg = args.get("eoj")
    object_code_arg = args.get("obj")
    interval = _normalize_int(
        args.get("interval", _DEFAULT_INTERVAL), _DEFAULT_INTERVAL, 1
    )
    duration = _normalize_int(
        args.get("duration", _DEFAULT_DURATION), _DEFAULT_DURATION, 1
    )
    timeout = _normalize_int(args.get("timeout", _DEFAULT_TIMEOUT), _DEFAULT_TIMEOUT, 1)
    output_format = str(args.get("fmt") or "json").strip().lower()

    if not ip_address:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_argument",
                    default="Error: ip_address is required.",
                ),
            },
        }
        return (
            payload["error"]["message"]
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    try:
        target_eoj_text, target_eoj_bytes, target_name = _resolve_target_eoj(
            eoj_arg, object_code_arg
        )
    except ValueError as exc:
        payload = {
            "ok": False,
            "error": {"code": "invalid_argument", "message": str(exc)},
        }
        return (
            payload["error"]["message"]
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    start = time.monotonic()
    deadline = start + duration
    previous_snapshot: dict[str, dict[str, Any]] | None = None
    all_changes: list[dict[str, Any]] = []
    polls = 0
    seen_response = False
    stopped_reason = "duration_elapsed"

    while True:
        now = time.monotonic()
        if now >= deadline:
            break
        remaining = max(1, int(deadline - now))
        poll_timeout = min(timeout, remaining)
        frames = _query_node(
            ip_address=ip_address,
            target_eoj=target_eoj_bytes,
            target_eoj_text=target_eoj_text,
            timeout=poll_timeout,
        )
        polls += 1
        if frames:
            seen_response = True
            current_snapshot = _snapshot_from_frames(frames)
            timestamp = _now_iso()
            changes = _snapshot_changes(
                previous_snapshot,
                current_snapshot,
                timestamp=timestamp,
                ip_address=ip_address,
                target_eoj=target_eoj_text,
                target_name=target_name,
            )
            all_changes.extend(changes)
            previous_snapshot = current_snapshot
        else:
            if previous_snapshot is None and not seen_response:
                stopped_reason = "no_response"

        next_tick = time.monotonic() + interval
        if next_tick >= deadline:
            break
        sleep_for = max(0.0, min(interval, deadline - time.monotonic()))
        if sleep_for > 0:
            time.sleep(sleep_for)

    elapsed_ms = int((time.monotonic() - start) * 1000)

    if not seen_response:
        payload = {
            "ok": False,
            "error": {
                "code": "timeout",
                "message": _(
                    "msg.no_response",
                    default="No ECHONET Lite response was received during monitoring.",
                ),
            },
            "target": {
                "ip": ip_address,
                "eoj": target_eoj_text,
                "obj": object_code_arg,
                "name": target_name,
            },
            "interval": interval,
            "duration": duration,
            "timeout": timeout,
            "polls": polls,
            "stopped_reason": stopped_reason,
            "elapsed_ms": elapsed_ms,
        }
        return (
            payload["error"]["message"]
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    payload = {
        "ok": True,
        "count": len(all_changes),
        "changes": all_changes,
        "target": {
            "ip": ip_address,
            "eoj": target_eoj_text,
            "obj": object_code_arg,
            "name": target_name,
        },
        "interval": interval,
        "duration": duration,
        "timeout": timeout,
        "polls": polls,
        "stopped_reason": stopped_reason,
        "elapsed_ms": elapsed_ms,
    }

    if output_format == "text":
        return _format_text(payload)
    return json.dumps(payload, ensure_ascii=False)
