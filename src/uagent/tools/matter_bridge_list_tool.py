from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._matter_common import error_payload, ok_payload, WarningCollector
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:matter_bridge_list"

_DEFAULT_OUTPUT_FORMAT = "json"
_ENV_BRIDGES_JSON = "UAGENT_MATTER_BRIDGES_JSON"
_ENV_BRIDGES_FILE = "UAGENT_MATTER_BRIDGES_FILE"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_bridge_list",
        "description": _(
            "tool.description",
            default=(
                "List Matter bridge-managed devices and return a JSON or text summary."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "bridge": {
                    "type": "string",
                    "description": _(
                        "param.bridge.description",
                        default=("Bridge ID (omit for all)."),
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": _DEFAULT_OUTPUT_FORMAT,
                    "description": _(
                        "param.fmt.description",
                        default="Format: json or text.",
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _extract_location(item: dict[str, Any]) -> dict[str, Any]:
    """Extract room/area/floor information from a raw item."""
    result: dict[str, Any] = {}
    room = (
        item.get("room")
        or item.get("area")
        or item.get("location")
        or item.get("zone")
        or item.get("roomName")
        or item.get("room_name")
        or item.get("areaName")
        or item.get("area_name")
        or item.get("locationName")
        or item.get("location_name")
    )
    if room is not None:
        result["room"] = str(room)
    section = item.get("area") or item.get("zone") or item.get("section")
    if section is not None and str(section) != str(room):
        result["area"] = str(section)
    floor = item.get("floor") or item.get("floorNumber") or item.get("floor_number")
    if floor is not None:
        try:
            result["floor"] = int(floor)
        except (ValueError, TypeError):
            result["floor"] = str(floor)
    return result


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().casefold()
        if raw in {"1", "true", "yes", "on", "online", "reachable"}:
            return True
        if raw in {"0", "false", "no", "off", "offline", "unreachable"}:
            return False
    return None


def _load_bridges_payload() -> tuple[list[dict[str, Any]], str]:
    file_path = os.getenv(_ENV_BRIDGES_FILE, "").strip()
    if file_path:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            data = json.loads(text)
            return _extract_bridges(data), f"file:{file_path}"
        except FileNotFoundError:
            raise FileNotFoundError(
                _(
                    "err.config_missing",
                    default=(
                        "Matter bridge configuration file was not found. Set {env_json} or {env_file}."
                    ),
                    env_json=_ENV_BRIDGES_JSON,
                    env_file=_ENV_BRIDGES_FILE,
                )
            )
        except Exception as exc:
            raise ValueError(
                _(
                    "err.invalid_config",
                    default=("Matter bridge configuration could not be parsed: {err}"),
                    err=str(exc),
                )
            ) from exc

    raw_json = os.getenv(_ENV_BRIDGES_JSON, "").strip()
    if not raw_json:
        raise FileNotFoundError(
            _(
                "err.config_missing",
                default=(
                    "Matter bridge configuration is missing. Set {env_json} or {env_file}."
                ),
                env_json=_ENV_BRIDGES_JSON,
                env_file=_ENV_BRIDGES_FILE,
            )
        )

    try:
        data = json.loads(raw_json)
    except Exception as exc:
        raise ValueError(
            _(
                "err.invalid_config",
                default=("Matter bridge configuration could not be parsed: {err}"),
                err=str(exc),
            )
        ) from exc
    return _extract_bridges(data), f"env:{_ENV_BRIDGES_JSON}"


def _extract_bridges(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("bridges", "bridgeList", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if all(isinstance(value, dict) for value in data.values()):
            return [value for value in data.values() if isinstance(value, dict)]
        if any(isinstance(value, list) for value in data.values()):
            items: list[dict[str, Any]] = []
            for value in data.values():
                if isinstance(value, list):
                    items.extend(item for item in value if isinstance(item, dict))
            if items:
                return items
    return []


def _normalize_bridge_item(item: dict[str, Any]) -> dict[str, Any]:
    devices = item.get("devices") if isinstance(item.get("devices"), list) else []
    device_count = item.get("deviceCount")
    if device_count is None:
        device_count = item.get("device_count")
    if device_count is None and isinstance(devices, list):
        device_count = len([x for x in devices if isinstance(x, dict)])

    reachable = _as_bool(
        item.get("reachable")
        if item.get("reachable") is not None
        else (
            item.get("online")
            if item.get("online") is not None
            else item.get("connected")
        )
    )

    bridge_id = item.get("bridgeId") or item.get("bridge") or item.get("id")
    bridge_name = item.get("bridgeName") or item.get("bridge_name") or item.get("name")
    controller_id = item.get("controllerId") or item.get("ctrl")

    location = _extract_location(item)
    return {
        "bridge": bridge_id,
        "bridge_name": bridge_name,
        "ctrl": controller_id,
        "device_count": device_count,
        "device_ids": _normalize_id_list(
            item.get("deviceIds")
            or item.get("device_ids")
            or item.get("devices")
            or item.get("deviceList")
        ),
        "room": location.get("room"),
        "area": location.get("area"),
        "floor": location.get("floor"),
        "transport": item.get("transport")
        or item.get("connectionType")
        or item.get("connection_type"),
        "reachable": reachable,
        "last_updated": item.get("lastUpdated")
        or item.get("last_updated")
        or item.get("updatedAt")
        or item.get("updated_at"),
        "source": item.get("source"),
        "raw": item,
    }


def _normalize_id_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                ident = (
                    item.get("deviceId")
                    or item.get("dev")
                    or item.get("id")
                    or item.get("bridgeId")
                    or item.get("bridge")
                )
                if ident is not None and str(ident).strip():
                    items.append(str(ident))
            else:
                text = str(item).strip()
                if text:
                    items.append(text)
        return items
    if isinstance(value, str):
        raw = value.strip()
        return [raw] if raw else []
    return []


def _filter_bridges(
    items: list[dict[str, Any]], bridge_id: str | None
) -> list[dict[str, Any]]:
    if not bridge_id:
        return items
    needle = bridge_id.strip().casefold()
    if not needle:
        return items
    filtered: list[dict[str, Any]] = []
    for item in items:
        bid = str(item.get("bridge") or "").casefold()
        bname = str(item.get("bridge_name") or "").casefold()
        if needle in bid or needle in bname:
            filtered.append(item)
    return filtered


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    bridge = result.get("bridge", {})
    lines = [
        f"Matter bridges: {result.get('count', 0)}",
        f"Scope: {bridge.get('scope', 'all')}",
        f"Source: {bridge.get('source', '')}",
        f"Fetched at: {result.get('fetched_at', '')}",
    ]
    for item in result.get("items", []):
        room = item.get("room") or ""
        loc = f" [{room}]" if room else ""
        lines.append(
            "- {name}{loc} (id={bid}) devices={count} controller={controller} reachable={reachable}".format(
                name=item.get("bridge_name") or "(unknown)",
                loc=loc,
                bid=item.get("bridge") or "(unknown)",
                count=item.get("device_count"),
                controller=item.get("ctrl") or "-",
                reachable=item.get("reachable"),
            )
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or _DEFAULT_OUTPUT_FORMAT).lower()
    bridge_id = args.get("bridge")

    try:
        bridges_raw, source = _load_bridges_payload()
    except FileNotFoundError as exc:
        payload = error_payload("config_missing", str(exc))
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
    except ValueError as exc:
        payload = error_payload("invalid_config", str(exc))
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
    except Exception as exc:
        payload = error_payload("request_failed", str(exc))
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    items = [_normalize_bridge_item(item) for item in bridges_raw]
    filtered = _filter_bridges(items, str(bridge_id) if bridge_id is not None else None)

    if bridge_id and not filtered:
        payload = error_payload(
            "not_found",
            _(
                "err.not_found",
                default=("Matter bridge not found: {bridge_id}"),
                bridge_id=str(bridge_id),
            ),
            extra_top={
                "bridge": {
                    "scope": "filtered",
                    "bridge": str(bridge_id),
                    "source": source,
                },
                "fetched_at": _now_iso(),
            },
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    result = {
        "ok": True,
        "count": len(filtered),
        "items": filtered,
        "bridge": {
            "scope": "filtered" if bridge_id else "all",
            "bridge": str(bridge_id) if bridge_id is not None else None,
            "total": len(items),
            "source": source,
        },
        "fetched_at": _now_iso(),
        "raw": {
            "source": source,
            "total": len(items),
        },
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
