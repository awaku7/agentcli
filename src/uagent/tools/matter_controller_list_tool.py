from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._matter_cache import matter_cache_get, matter_cache_put
from ._matter_common import error_payload, ok_payload, WarningCollector
import time
from ._matter_log import matter_log
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:matter_controller_list"

_DEFAULT_OUTPUT_FORMAT = "json"
_ENV_CONTROLLERS_JSON = "UAGENT_MATTER_CONTROLLERS_JSON"
_ENV_CONTROLLERS_FILE = "UAGENT_MATTER_CONTROLLERS_FILE"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_controller_list",
        "description": _(
            "tool.description",
            default=(
                "List Matter controller-managed devices and return a JSON or text summary."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ctrl": {
                    "type": "string",
                    "description": _(
                        "param.ctrl.description",
                        default=("Controller ID (omit for all)."),
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


def _load_controllers_payload() -> tuple[list[dict[str, Any]], str]:
    file_path = os.getenv(_ENV_CONTROLLERS_FILE, "").strip()
    if file_path:
        try:
            text = Path(file_path).read_text(encoding="utf-8")
            data = json.loads(text)
            return _extract_controllers(data), f"file:{file_path}"
        except FileNotFoundError:
            raise FileNotFoundError(
                _(
                    "err.config_missing",
                    default=(
                        "Matter controller configuration file was not found. Set {env_json} or {env_file}."
                    ),
                    env_json=_ENV_CONTROLLERS_JSON,
                    env_file=_ENV_CONTROLLERS_FILE,
                )
            )
        except Exception as exc:
            raise ValueError(
                _(
                    "err.invalid_config",
                    default=(
                        "Matter controller configuration could not be parsed: {err}"
                    ),
                    err=str(exc),
                )
            ) from exc

    raw_json = os.getenv(_ENV_CONTROLLERS_JSON, "").strip()
    if not raw_json:
        raise FileNotFoundError(
            _(
                "err.config_missing",
                default=(
                    "Matter controller configuration is missing. Set {env_json} or {env_file}."
                ),
                env_json=_ENV_CONTROLLERS_JSON,
                env_file=_ENV_CONTROLLERS_FILE,
            )
        )

    try:
        data = json.loads(raw_json)
    except Exception as exc:
        raise ValueError(
            _(
                "err.invalid_config",
                default=("Matter controller configuration could not be parsed: {err}"),
                err=str(exc),
            )
        ) from exc
    return _extract_controllers(data), f"env:{_ENV_CONTROLLERS_JSON}"


def _extract_controllers(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("controllers", "controllerList", "items", "data"):
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


def _normalize_bridge_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        return [raw] if raw else []
    return []


def _normalize_controller_item(item: dict[str, Any]) -> dict[str, Any]:
    bridge_ids = _normalize_bridge_ids(
        item.get("bridgeIds")
        or item.get("bridge_ids")
        or item.get("bridges")
        or item.get("bridgeList")
    )
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

    controller_id = item.get("controllerId") or item.get("ctrl") or item.get("id")
    controller_name = (
        item.get("controllerName") or item.get("controller_name") or item.get("name")
    )

    location = _extract_location(item)
    normalized = {
        "ctrl": controller_id,
        "controller_name": controller_name,
        "device_count": device_count,
        "bridge_ids": bridge_ids,
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
    return normalized


def _filter_controllers(
    items: list[dict[str, Any]], controller_id: str | None
) -> list[dict[str, Any]]:
    if not controller_id:
        return items
    needle = controller_id.strip().casefold()
    if not needle:
        return items
    filtered: list[dict[str, Any]] = []
    for item in items:
        cid = str(item.get("ctrl") or "").casefold()
        cname = str(item.get("controller_name") or "").casefold()
        if needle in cid or needle in cname:
            filtered.append(item)
    return filtered


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    controller = result.get("controller", {})
    lines = [
        f"Matter controllers: {result.get('count', 0)}",
        f"Scope: {controller.get('scope', 'all')}",
        f"Source: {controller.get('source', '')}",
        f"Fetched at: {result.get('fetched_at', '')}",
    ]
    for item in result.get("items", []):
        room = item.get("room") or ""
        loc = f" [{room}]" if room else ""
        lines.append(
            "- {name}{loc} (id={cid}) devices={count} bridges={bridges} reachable={reachable}".format(
                name=item.get("controller_name") or "(unknown)",
                loc=loc,
                cid=item.get("ctrl") or "(unknown)",
                count=item.get("device_count"),
                bridges=",".join(item.get("bridge_ids") or []) or "-",
                reachable=item.get("reachable"),
            )
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    _log_start = time.time()
    output_format = str(args.get("fmt") or _DEFAULT_OUTPUT_FORMAT).lower()
    controller_id = args.get("ctrl")


    cache_key = ":".join([str(args.get("ctrl", "") or "")])
    cached = matter_cache_get("matter_controller_list", cache_key)
    if cached is not None:
        if str(args.get("fmt") or "json").lower() == "text":
            return _format_text(cached)
        return json.dumps(cached, ensure_ascii=False)
    try:
        controllers_raw, source = _load_controllers_payload()
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

    items = [_normalize_controller_item(item) for item in controllers_raw]
    filtered = _filter_controllers(
        items, str(controller_id) if controller_id is not None else None
    )

    if controller_id and not filtered:
        payload = error_payload(
            "not_found",
            _(
                "err.not_found",
                default=("Matter controller not found: {controller_id}"),
                controller_id=str(controller_id),
            ),
            extra_top={
                "controller": {
                    "scope": "filtered",
                    "ctrl": str(controller_id),
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

    result = ok_payload({
        "count": len(filtered),
        "items": filtered,
        "controller": {
            "scope": "filtered" if controller_id else "all",
            "ctrl": str(controller_id) if controller_id is not None else None,
            "total": len(items),
            "source": source,
        },
        "fetched_at": _now_iso(),
        "raw": {
            "source": source,
            "total": len(items),
        },
    })
    matter_cache_put("matter_controller_list", cache_key, result)
    matter_log("matter_controller_list", args, ok=True, elapsed_ms=(time.time() - _log_start) * 1000)
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
