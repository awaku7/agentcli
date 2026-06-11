from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:matter_endpoint_list"

_DEFAULT_OUTPUT_FORMAT = "json"
_ENV_CONTROLLERS_JSON = "UAGENT_MATTER_CONTROLLERS_JSON"
_ENV_CONTROLLERS_FILE = "UAGENT_MATTER_CONTROLLERS_FILE"
_ENV_BRIDGES_JSON = "UAGENT_MATTER_BRIDGES_JSON"
_ENV_BRIDGES_FILE = "UAGENT_MATTER_BRIDGES_FILE"
_ENV_DEVICES_JSON = "UAGENT_MATTER_DEVICES_JSON"
_ENV_DEVICES_FILE = "UAGENT_MATTER_DEVICES_FILE"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "matter_endpoint_list",
        "description": _(
            "tool.description",
            default="List Matter device endpoints and return a JSON or text summary.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": _(
                        "param.device_id.description",
                        default="Matter device ID to look up. Required identifier.",
                    ),
                },
                "controller_id": {
                    "type": "string",
                    "description": _(
                        "param.controller_id.description",
                        default=(
                            "Optional controller ID filter. Helps disambiguate the target device."
                        ),
                    ),
                },
                "bridge_id": {
                    "type": "string",
                    "description": _(
                        "param.bridge_id.description",
                        default=(
                            "Optional bridge ID filter. Helps disambiguate the target device."
                        ),
                    ),
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": _DEFAULT_OUTPUT_FORMAT,
                    "description": _(
                        "param.output_format.description",
                        default="Output format: JSON or human-readable text.",
                    ),
                },
            },
            "required": ["device_id"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        raw = value.strip().casefold()
        if raw in {"1", "true", "yes", "on", "online", "reachable", "connected"}:
            return True
        if raw in {"0", "false", "no", "off", "offline", "unreachable", "disconnected"}:
            return False
    return None


def _load_payload_from_env(
    json_env: str, file_env: str
) -> tuple[Any | None, str | None]:
    file_path = os.getenv(file_env, "").strip()
    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")
        return json.loads(text), f"file:{file_path}"
    raw_json = os.getenv(json_env, "").strip()
    if raw_json:
        return json.loads(raw_json), f"env:{json_env}"
    return None, None


def _extract_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("devices", "deviceList", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if any(isinstance(value, list) for value in data.values()):
        items: list[dict[str, Any]] = []
        for value in data.values():
            if isinstance(value, list):
                items.extend(item for item in value if isinstance(item, dict))
        if items:
            return items
    if any(k in data for k in ("deviceId", "device_id", "deviceName", "device_name")):
        return [data]
    return []


def _normalize_cluster_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_id": item.get("clusterId") or item.get("cluster_id") or item.get("id"),
        "cluster_name": item.get("clusterName")
        or item.get("cluster_name")
        or item.get("name"),
        "attributes": (
            item.get("attributes")
            if isinstance(item.get("attributes"), list)
            else item.get("attributeList")
        ),
        "commands": (
            item.get("commands")
            if isinstance(item.get("commands"), list)
            else item.get("commandList")
        ),
        "raw": item,
    }


def _normalize_endpoint_item(item: dict[str, Any]) -> dict[str, Any]:
    clusters = (
        item.get("clusters")
        if isinstance(item.get("clusters"), list)
        else item.get("clusterList")
    )
    normalized_clusters = (
        [
            _normalize_cluster_item(cluster)
            for cluster in clusters
            if isinstance(cluster, dict)
        ]
        if isinstance(clusters, list)
        else []
    )
    return {
        "endpoint_id": item.get("endpointId")
        or item.get("endpoint_id")
        or item.get("id"),
        "device_type": item.get("deviceType") or item.get("device_type"),
        "clusters": normalized_clusters,
        "raw": item,
    }


def _normalize_device_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    endpoints_raw = (
        item.get("endpoints")
        if isinstance(item.get("endpoints"), list)
        else item.get("endpointList")
    )
    endpoints = (
        [
            _normalize_endpoint_item(endpoint)
            for endpoint in endpoints_raw
            if isinstance(endpoint, dict)
        ]
        if isinstance(endpoints_raw, list)
        else []
    )
    clusters_raw = (
        item.get("clusters")
        if isinstance(item.get("clusters"), list)
        else item.get("clusterList")
    )
    clusters = (
        [
            _normalize_cluster_item(cluster)
            for cluster in clusters_raw
            if isinstance(cluster, dict)
        ]
        if isinstance(clusters_raw, list)
        else []
    )
    status = item.get("status") if isinstance(item.get("status"), dict) else None
    if status is None:
        status = item.get("state") if isinstance(item.get("state"), dict) else None

    return {
        "device_id": item.get("deviceId") or item.get("device_id") or item.get("id"),
        "device_name": item.get("deviceName")
        or item.get("device_name")
        or item.get("name"),
        "device_type": item.get("deviceType")
        or item.get("device_type")
        or item.get("type")
        or source,
        "vendor": item.get("vendor")
        or item.get("manufacturer")
        or item.get("manufacturerName")
        or item.get("manufacturer_name"),
        "bridge_id": item.get("bridgeId") or item.get("bridge_id"),
        "controller_id": item.get("controllerId") or item.get("controller_id"),
        "reachable": _as_bool(
            item.get("reachable")
            if item.get("reachable") is not None
            else (
                item.get("online")
                if item.get("online") is not None
                else item.get("connected")
            )
        ),
        "last_updated": item.get("lastUpdated")
        or item.get("last_updated")
        or item.get("updatedAt")
        or item.get("updated_at"),
        "endpoints": endpoints,
        "clusters": clusters,
        "status": status,
        "source": source,
        "raw": item,
    }


def _iter_device_candidates(payloads: list[tuple[Any, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for data, source in payloads:
        for item in _extract_items(data):
            normalized = _normalize_device_item(item, source)
            key = (
                str(normalized.get("device_id") or "").casefold(),
                str(normalized.get("controller_id") or "").casefold(),
                str(normalized.get("bridge_id") or "").casefold(),
            )
            if not key[0]:
                continue
            if key in seen:
                continue
            seen.add(key)
            items.append(normalized)
    return items


def _filter_candidates(
    items: list[dict[str, Any]],
    *,
    device_id: str,
    controller_id: str | None,
    bridge_id: str | None,
) -> list[dict[str, Any]]:
    device_key = device_id.strip().casefold()
    controller_key = controller_id.strip().casefold() if controller_id else None
    bridge_key = bridge_id.strip().casefold() if bridge_id else None

    filtered: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("device_id") or "").casefold() != device_key:
            continue
        if (
            controller_key
            and str(item.get("controller_id") or "").casefold() != controller_key
        ):
            continue
        if bridge_key and str(item.get("bridge_id") or "").casefold() != bridge_key:
            continue
        filtered.append(item)
    return filtered


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    device = result.get("device", {})
    lines = [
        f"Matter device endpoints: {result.get('count', 0)}",
        f"Device: {device.get('device_name') or '(unknown)'}",
        f"Device ID: {device.get('device_id') or '(unknown)'}",
        f"Type: {device.get('device_type') or '(unknown)'}",
        f"Vendor: {device.get('vendor') or '-'}",
        f"Controller: {device.get('controller_id') or '-'}",
        f"Bridge: {device.get('bridge_id') or '-'}",
        f"Reachable: {device.get('reachable')}",
        f"Fetched at: {result.get('fetched_at', '')}",
    ]
    endpoints = result.get("endpoints") or []
    for endpoint in endpoints:
        clusters = endpoint.get("clusters") or []
        lines.append(
            "- endpoint {eid} type={dtype} clusters={count}".format(
                eid=endpoint.get("endpoint_id") or "(unknown)",
                dtype=endpoint.get("device_type") or "-",
                count=len(clusters),
            )
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("output_format") or _DEFAULT_OUTPUT_FORMAT).lower()
    device_id = str(args.get("device_id") or "").strip()
    controller_id = args.get("controller_id")
    bridge_id = args.get("bridge_id")

    if not device_id:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.device_id_required",
                    default="Matter device ID is required.",
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    payloads: list[tuple[Any, str]] = []
    for json_env, file_env in (
        (_ENV_DEVICES_JSON, _ENV_DEVICES_FILE),
        (_ENV_CONTROLLERS_JSON, _ENV_CONTROLLERS_FILE),
        (_ENV_BRIDGES_JSON, _ENV_BRIDGES_FILE),
    ):
        try:
            data, source = _load_payload_from_env(json_env, file_env)
        except FileNotFoundError:
            continue
        except ValueError as exc:
            payload = {
                "ok": False,
                "error": {
                    "code": "invalid_config",
                    "message": str(exc),
                },
            }
            return (
                _format_text(payload)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )
        if data is not None and source is not None:
            payloads.append((data, source))

    if not payloads:
        payload = {
            "ok": False,
            "error": {
                "code": "config_missing",
                "message": _(
                    "err.config_missing",
                    default=(
                        "Matter device data is missing. Set {env_json} or {env_file} for devices, controllers, or bridges."
                    ),
                    env_json=_ENV_DEVICES_JSON,
                    env_file=_ENV_DEVICES_FILE,
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    candidates = _iter_device_candidates(payloads)
    filtered = _filter_candidates(
        candidates,
        device_id=device_id,
        controller_id=str(controller_id) if controller_id is not None else None,
        bridge_id=str(bridge_id) if bridge_id is not None else None,
    )

    if not filtered:
        payload = {
            "ok": False,
            "error": {
                "code": "not_found",
                "message": _(
                    "err.not_found",
                    default="Matter device not found: {device_id}",
                    device_id=device_id,
                ),
            },
            "device": {
                "device_id": device_id,
                "controller_id": (
                    str(controller_id) if controller_id is not None else None
                ),
                "bridge_id": str(bridge_id) if bridge_id is not None else None,
            },
            "fetched_at": _now_iso(),
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if len(filtered) > 1:
        payload = {
            "ok": False,
            "error": {
                "code": "ambiguous_target",
                "message": _(
                    "err.ambiguous_target",
                    default="Matter device target is ambiguous: {device_id}",
                    device_id=device_id,
                ),
                "candidates": [
                    {
                        "device_id": item.get("device_id"),
                        "device_name": item.get("device_name"),
                        "controller_id": item.get("controller_id"),
                        "bridge_id": item.get("bridge_id"),
                    }
                    for item in filtered[:10]
                ],
            },
            "device": {
                "device_id": device_id,
                "controller_id": (
                    str(controller_id) if controller_id is not None else None
                ),
                "bridge_id": str(bridge_id) if bridge_id is not None else None,
            },
            "fetched_at": _now_iso(),
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    item = filtered[0]
    endpoints = item.get("endpoints") or []
    result = {
        "ok": True,
        "count": len(endpoints),
        "items": endpoints,
        "endpoints": endpoints,
        "device": {
            "device_id": item.get("device_id"),
            "device_name": item.get("device_name"),
            "device_type": item.get("device_type"),
            "vendor": item.get("vendor"),
            "bridge_id": item.get("bridge_id"),
            "controller_id": item.get("controller_id"),
            "reachable": item.get("reachable"),
            "last_updated": item.get("last_updated"),
            "source": item.get("source"),
        },
        "fetched_at": _now_iso(),
        "raw": {
            "source": item.get("source"),
        },
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
