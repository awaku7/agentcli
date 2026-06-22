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
STATUS_LABEL = "tool:matter_control"

_DEFAULT_OUTPUT_FORMAT = "json"
_ENV_CONTROLLERS_JSON = "UAGENT_MATTER_CONTROLLERS_JSON"
_ENV_CONTROLLERS_FILE = "UAGENT_MATTER_CONTROLLERS_FILE"
_ENV_BRIDGES_JSON = "UAGENT_MATTER_BRIDGES_JSON"
_ENV_BRIDGES_FILE = "UAGENT_MATTER_BRIDGES_FILE"
_ENV_DEVICES_JSON = "UAGENT_MATTER_DEVICES_JSON"
_ENV_DEVICES_FILE = "UAGENT_MATTER_DEVICES_FILE"
_ENV_COMMAND_ENV = "UAGENT_MATTER_COMMAND_JSON"
_ENV_COMMAND_FILE = "UAGENT_MATTER_COMMAND_FILE"

ACTIONS_ON_OFF = frozenset({"on", "off"})
ACTIONS_OPEN_CLOSE = frozenset({"open", "close"})
ACTIONS_LOCK = frozenset({"lock", "unlock"})
ACTIONS_SET_VALUE = frozenset({"set_value"})
ALL_ACTIONS = ACTIONS_ON_OFF | ACTIONS_OPEN_CLOSE | ACTIONS_LOCK | ACTIONS_SET_VALUE

# Device type -> supported actions mapping (lowercase matching)
_DEVICE_ACTIONS: dict[str, frozenset[str]] = {
    "light": ACTIONS_ON_OFF | frozenset({"set_value"}),
    "lighting": ACTIONS_ON_OFF | frozenset({"set_value"}),
    "switch": ACTIONS_ON_OFF,
    "outlet": ACTIONS_ON_OFF,
    "plug": ACTIONS_ON_OFF,
    "fan": ACTIONS_ON_OFF | frozenset({"set_value"}),
    "lock": ACTIONS_LOCK,
    "thermostat": ACTIONS_ON_OFF | frozenset({"set_value"}),
    "climate": ACTIONS_ON_OFF | frozenset({"set_value"}),
    "cover": ACTIONS_OPEN_CLOSE | frozenset({"set_value"}),
    "curtain": ACTIONS_OPEN_CLOSE | frozenset({"set_value"}),
    "blind": ACTIONS_OPEN_CLOSE | frozenset({"set_value"}),
    "shade": ACTIONS_OPEN_CLOSE | frozenset({"set_value"}),
    "window": ACTIONS_OPEN_CLOSE | frozenset({"set_value"}),
    "sensor": frozenset(),
    "temperature_sensor": frozenset(),
    "humidity_sensor": frozenset(),
}

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "matter_control",
        "description": _(
            "tool.description",
            default="Control a Matter device (on/off/open/close/lock/unlock/set_value).",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dev": {
                    "type": "string",
                    "description": _(
                        "param.dev.description",
                        default="Device ID (required).",
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": sorted(ALL_ACTIONS),
                    "description": _(
                        "param.action.description",
                        default="Action.",
                    ),
                },
                "value": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": _(
                        "param.value.description",
                        default="Value (0-100).",
                    ),
                },
                "ctrl": {
                    "type": "string",
                    "description": _(
                        "param.ctrl.description",
                        default=("Controller ID (optional)."),
                    ),
                },
                "bridge": {
                    "type": "string",
                    "description": _(
                        "param.bridge.description",
                        default=("Bridge ID (optional)."),
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": _(
                        "param.dry_run.description",
                        default=(
                            "If true, validate the command without queueing it. "
                            "Default: false."
                        ),
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
            "required": ["device_id", "action"],
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


def _normalize_device_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "dev": item.get("deviceId") or item.get("dev") or item.get("id"),
        "devname": item.get("deviceName") or item.get("devname") or item.get("name"),
        "device_type": item.get("deviceType")
        or item.get("device_type")
        or item.get("type")
        or source,
        "vendor": item.get("vendor")
        or item.get("manufacturer")
        or item.get("manufacturerName")
        or item.get("manufacturer_name"),
        "bridge": item.get("bridgeId") or item.get("bridge"),
        "ctrl": item.get("controllerId") or item.get("ctrl"),
        "reachable": _as_bool(
            item.get("reachable")
            if item.get("reachable") is not None
            else (
                item.get("online")
                if item.get("online") is not None
                else item.get("connected")
            )
        ),
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
                str(normalized.get("dev") or "").casefold(),
                str(normalized.get("ctrl") or "").casefold(),
                str(normalized.get("bridge") or "").casefold(),
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
        if str(item.get("dev") or "").casefold() != device_key:
            continue
        if controller_key and str(item.get("ctrl") or "").casefold() != controller_key:
            continue
        if bridge_key and str(item.get("bridge") or "").casefold() != bridge_key:
            continue
        filtered.append(item)
    return filtered


def _get_supported_actions(device_type: str | None) -> frozenset[str]:
    if not device_type:
        return frozenset()
    dtype_lower = str(device_type).casefold()
    # Exact match first, then partial match
    if dtype_lower in _DEVICE_ACTIONS:
        return _DEVICE_ACTIONS[dtype_lower]
    for pattern, actions in _DEVICE_ACTIONS.items():
        if pattern in dtype_lower:
            return actions
    return frozenset()


def _validate_action(
    action: str, supported: frozenset[str], device_type: str | None
) -> str | None:
    if action not in ALL_ACTIONS:
        return _(
            "err.invalid_action",
            default="Invalid action: {action}. Allowed: {allowed}",
            action=action,
            allowed=", ".join(sorted(ALL_ACTIONS)),
        )
    if not supported:
        return _(
            "err.unsupported_device",
            default=(
                "Device type '{device_type}' does not support any control actions."
            ),
            device_type=device_type or "unknown",
        )
    if action not in supported:
        return _(
            "err.action_not_supported",
            default=(
                "Action '{action}' is not supported for device type '{device_type}'. "
                "Supported: {supported}"
            ),
            action=action,
            device_type=device_type or "unknown",
            supported=", ".join(sorted(supported)),
        )
    return None


def _queue_command(command: dict[str, Any]) -> tuple[bool, str]:
    """Queue a control command via environment variable or file.

    Returns (success, source_description).
    """
    command_json = json.dumps(command, ensure_ascii=False)

    # Priority 1: write to command file
    file_path = os.getenv(_ENV_COMMAND_FILE, "").strip()
    if file_path:
        try:
            Path(file_path).write_text(command_json, encoding="utf-8")
            return True, f"file:{file_path}"
        except OSError as exc:
            return False, str(exc)

    # Priority 2: write to command environment variable
    try:
        os.environ[_ENV_COMMAND_ENV] = command_json
        return True, f"env:{_ENV_COMMAND_ENV}"
    except Exception as exc:
        return False, str(exc)


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    command = result.get("command", {})
    device = result.get("device", {})
    lines = [
        f"Matter control command queued: {command.get('action', '?')}",
        f"Device: {device.get('device_name') or '(unknown)'}",
        f"Device ID: {device.get('device_id') or '(unknown)'}",
        f"Type: {device.get('device_type') or '(unknown)'}",
        f"Action: {command.get('action')}",
    ]
    if command.get("value") is not None:
        lines.append(f"Value: {command['value']}")
    lines.append(f"Queued to: {command.get('queued_to') or '-'}")
    lines.append(f"Fetched at: {result.get('fetched_at', '')}")
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or _DEFAULT_OUTPUT_FORMAT).lower()
    device_id = str(args.get("dev") or "").strip()
    action = str(args.get("action") or "").strip().casefold()
    controller_id = args.get("ctrl")
    bridge_id = args.get("bridge")
    value = args.get("value")
    dry_run = bool(args.get("dry_run", False))

    # Validate required inputs
    if not device_id:
        payload = error_payload(
            "invalid_argument",
            _(
                "err.device_id_required",
                default="Matter device ID is required.",
            ),
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if not action or action not in ALL_ACTIONS:
        payload = error_payload(
            "invalid_argument",
            _(
                "err.action_required",
                default=("A valid action is required: {allowed}"),
                allowed=", ".join(sorted(ALL_ACTIONS)),
            ),
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if action in ACTIONS_SET_VALUE and value is None:
        payload = error_payload(
            "invalid_argument",
            _(
                "err.value_required",
                default=(
                    "A numeric value (0-100) is required for action '{action}'."
                ),
                action=action,
            ),
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if value is not None:
        try:
            int_val = int(value)
            if int_val < 0 or int_val > 100:
                raise ValueError
            value = int_val
        except (ValueError, TypeError):
            payload = error_payload(
                "invalid_argument",
                _(
                    "err.value_out_of_range",
                    default="Value must be an integer between 0 and 100.",
                ),
            )
            return (
                _format_text(payload)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

    # Load device config
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
            payload = error_payload("invalid_config", str(exc))
            return (
                _format_text(payload)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )
        if data is not None and source is not None:
            payloads.append((data, source))

    if not payloads:
        payload = error_payload(
            "config_missing",
            _(
                "err.config_missing",
                default=(
                    "Matter device data is missing. Set {env_json} or {env_file} for devices, controllers, or bridges."
                ),
                env_json=_ENV_DEVICES_JSON,
                env_file=_ENV_DEVICES_FILE,
            ),
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    # Find target device
    candidates = _iter_device_candidates(payloads)
    filtered = _filter_candidates(
        candidates,
        device_id=device_id,
        controller_id=str(controller_id) if controller_id is not None else None,
        bridge_id=str(bridge_id) if bridge_id is not None else None,
    )

    if not filtered:
        payload = error_payload(
            "not_found",
            _(
                "err.not_found",
                default="Matter device not found: {device_id}",
                device_id=device_id,
            ),
            extra_top={
                "device": {
                    "dev": device_id,
                    "ctrl": (str(controller_id) if controller_id is not None else None),
                    "bridge": str(bridge_id) if bridge_id is not None else None,
                },
                "fetched_at": _now_iso(),
            },
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if len(filtered) > 1:
        payload = error_payload(
            "ambiguous_target",
            _(
                "err.ambiguous_target",
                default="Matter device target is ambiguous: {device_id}",
                device_id=device_id,
            ),
            extra_top={
                "candidates": [
                    {
                        "dev": item.get("dev"),
                        "devname": item.get("devname"),
                        "ctrl": item.get("ctrl"),
                        "bridge": item.get("bridge"),
                    }
                    for item in filtered[:10]
                ],
                "device": {
                    "dev": device_id,
                    "ctrl": (str(controller_id) if controller_id is not None else None),
                    "bridge": str(bridge_id) if bridge_id is not None else None,
                },
                "fetched_at": _now_iso(),
            },
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    item = filtered[0]
    device_type = item.get("device_type") or "unknown"
    supported = _get_supported_actions(device_type)
    validation_error = _validate_action(action, supported, device_type)

    if validation_error:
        payload = error_payload(
            "unsupported_action",
            validation_error,
            extra_top={
                "device": {
                    "dev": item.get("dev"),
                    "devname": item.get("devname"),
                    "device_type": device_type,
                    "ctrl": item.get("ctrl"),
                    "bridge": item.get("bridge"),
                },
                "fetched_at": _now_iso(),
            },
        )
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    # Build command
    command: dict[str, Any] = {
        "dev": item.get("dev"),
        "devname": item.get("devname"),
        "ctrl": item.get("ctrl"),
        "bridge": item.get("bridge"),
        "action": action,
        "value": value,
        "queued_at": _now_iso(),
    }

    if dry_run:
        # Validation only, no queueing
        result = {
            "ok": True,
            "message": _(
                "msg.dry_run",
                default="Dry run: command validated but not queued.",
            ),
            "command": {**command, "dry_run": True},
            "device": {
                "dev": item.get("dev"),
                "devname": item.get("devname"),
                "device_type": device_type,
                "ctrl": item.get("ctrl"),
                "bridge": item.get("bridge"),
                "reachable": item.get("reachable"),
            },
            "fetched_at": _now_iso(),
        }
        return (
            _format_text(result)
            if output_format == "text"
            else json.dumps(result, ensure_ascii=False)
        )

    # Queue the command
    queued, source_desc = _queue_command(command)
    if not queued:
        payload = error_payload(
            "queue_failed",
            _(
                "err.queue_failed",
                default="Failed to queue control command: {reason}",
                reason=source_desc,
            ),
            extra_top={
                "command": command,
                "device": {
                    "dev": item.get("dev"),
                    "devname": item.get("devname"),
                    "device_type": device_type,
                    "ctrl": item.get("ctrl"),
                    "bridge": item.get("bridge"),
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
        "command": {
            **command,
            "queued_to": source_desc,
        },
        "device": {
            "dev": item.get("dev"),
            "devname": item.get("devname"),
            "device_type": device_type,
            "ctrl": item.get("ctrl"),
            "bridge": item.get("bridge"),
            "reachable": item.get("reachable"),
        },
        "fetched_at": _now_iso(),
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
