from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:switchbot_cloud_control"

_API_BASE = "https://api.switch-bot.com/v1.1"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "switchbot_cloud_control",
        "description": _(
            "tool.description",
            default=(
                "Control a SwitchBot Cloud device from the configured account and return a JSON or text result."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dev": {
                    "type": "string",
                    "description": _(
                        "param.dev.description",
                        default=(
                            "SwitchBot device ID to look up. Preferred identifier."
                        ),
                    ),
                },
                "devname": {
                    "type": "string",
                    "description": _(
                        "param.devname.description",
                        default=(
                            "SwitchBot device name to look up when device_id is not provided."
                        ),
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "on",
                        "off",
                        "open",
                        "close",
                        "set_value",
                        "lock",
                        "unlock",
                        "brightness_up",
                        "brightness_down",
                    ],
                    "description": _(
                        "param.action.description",
                        default="Action: on/off/open/close/set_value/lock/unlock.",
                    ),
                },
                "value": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": _(
                        "param.value.description",
                        default=(
                            "Optional numeric value for set_value actions. Range: 0-100."
                        ),
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "cool", "dry", "fan", "heat"],
                    "description": _(
                        "param.mode.description",
                        default="AC mode: auto/cool/dry/fan/heat.",
                    ),
                },
                "fan": {
                    "type": "string",
                    "enum": ["auto", "low", "medium", "high"],
                    "description": _(
                        "param.fan.description",
                        default="AC fan: auto/low/medium/high.",
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 15,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default="HTTP timeout (seconds).",
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
            "required": ["action"],
            "additionalProperties": False,
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _get_credentials() -> tuple[str | None, str | None]:
    token = os.getenv("UAGENT_SWITCHBOT_TOKEN")
    secret = os.getenv("UAGENT_SWITCHBOT_SECRET")
    return token, secret


def _build_auth_headers(token: str, secret: str, body_text: str = "") -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex
    payload = f"{token}{timestamp}{nonce}{body_text}"
    sign = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "Content-Type": "application/json; charset=utf-8",
        "t": timestamp,
        "nonce": nonce,
        "sign": sign,
    }


def _request_json(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    token, secret = _get_credentials()
    if not token or not secret:
        return {
            "ok": False,
            "error": {
                "code": "config_missing",
                "message": _(
                    "err.config_missing",
                    default=(
                        "SwitchBot Cloud credentials are missing. Set UAGENT_SWITCHBOT_TOKEN and UAGENT_SWITCHBOT_SECRET."
                    ),
                ),
            },
        }

    body_text = json.dumps(body, ensure_ascii=False) if body is not None else ""
    headers = _build_auth_headers(token, secret, body_text=body_text)
    url = f"{_API_BASE}{path}"
    data = body_text.encode("utf-8") if body_text else None
    request = Request(url, headers=headers, method=method, data=data)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data_obj = json.loads(raw or "{}")
    except HTTPError as exc:
        body_text = (
            exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        )
        try:
            detail = json.loads(body_text) if body_text else {}
        except Exception:
            detail = {"message": body_text or str(exc)}
        return {
            "ok": False,
            "error": {
                "code": f"http_{exc.code}",
                "message": detail.get("message") or str(exc),
                "detail": detail,
            },
        }
    except URLError as exc:
        return {
            "ok": False,
            "error": {
                "code": "network_error",
                "message": str(exc.reason if hasattr(exc, "reason") else exc),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": "request_failed",
                "message": str(exc),
            },
        }

    if not isinstance(data_obj, dict):
        return {
            "ok": False,
            "error": {
                "code": "invalid_response",
                "message": _(
                    "err.invalid_response",
                    default="SwitchBot Cloud returned an unexpected payload.",
                ),
            },
        }
    return {"ok": True, "data": data_obj}


def _extract_body(data: dict[str, Any]) -> dict[str, Any]:
    body = data.get("body")
    if isinstance(body, dict):
        return body
    return data


def _device_sections(body: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    for key in (
        "deviceList",
        "infraredRemoteList",
        "blindTiltList",
        "meterList",
        "curtainList",
    ):
        value = body.get(key)
        if isinstance(value, list):
            cleaned = [item for item in value if isinstance(item, dict)]
            if cleaned:
                sections.append((key, cleaned))
    if sections:
        return sections
    for key, value in body.items():
        if isinstance(value, list):
            cleaned = [item for item in value if isinstance(item, dict)]
            if cleaned:
                sections.append((key, cleaned))
    return sections


def _normalize_device_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "dev": item.get("deviceId") or item.get("dev"),
        "devname": item.get("deviceName") or item.get("devname"),
        "device_type": item.get("deviceType") or item.get("device_type") or source,
        "hub_id": item.get("hubDeviceId") or item.get("hub_id"),
        "room_id": item.get("roomId") or item.get("room_id"),
        "model": item.get("model"),
        "firmware": item.get("firmware"),
        "online": item.get("online"),
        "battery": item.get("battery"),
        "last_updated": item.get("lastUpdated") or item.get("last_updated"),
        "source": source,
        "raw": item,
    }


def _normalize_status_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "power": item.get("power"),
        "mode": item.get("mode"),
        "temperature": item.get("temperature"),
        "humidity": item.get("humidity"),
        "battery": item.get("battery"),
        "position": item.get("position"),
        "light_level": item.get("lightLevel") or item.get("light_level"),
        "fan": item.get("fanSpeed") or item.get("fan"),
        "lock_state": item.get("lockState") or item.get("lock_state"),
        "child_lock": item.get("childLock") or item.get("child_lock"),
        "raw": item,
    }


def _find_device(
    items: list[dict[str, Any]],
    device_id: str | None,
    device_name: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not device_id and not device_name:
        return None, {
            "code": "invalid_argument",
            "message": _(
                "err.invalid_arguments",
                default="Either device_id or device_name is required.",
            ),
        }

    if device_id:
        target = device_id.casefold()
        for item in items:
            candidate = str(item.get("dev") or "").casefold()
            if candidate == target:
                return item, None
        return None, {
            "code": "not_found",
            "message": _(
                "err.not_found",
                default="No SwitchBot device matched the provided device_id.",
                device_id=device_id,
            ),
        }

    assert device_name is not None
    needle = device_name.casefold()
    matches = [
        item
        for item in items
        if needle in str(item.get("devname") or "").casefold()
    ]
    if not matches:
        return None, {
            "code": "not_found",
            "message": _(
                "err.not_found",
                default="No SwitchBot device matched the provided device_name.",
                device_name=device_name,
            ),
        }
    if len(matches) > 1:
        return None, {
            "code": "ambiguous_target",
            "message": _(
                "err.ambiguous_target",
                default="Multiple SwitchBot devices matched the provided device_name.",
                device_name=device_name,
            ),
            "matches": [
                {
                    "devname": item.get("devname"),
                    "dev": item.get("dev"),
                }
                for item in matches[:10]
            ],
        }
    return matches[0], None


def _device_type_text(device_type: str | None) -> str:
    return str(device_type or "").casefold()


def _action_for_device(
    *,
    device_type: str | None,
    action: str,
    value: int | None,
    remote_type: str | None = None,
    mode: str | None = None,
    fan_speed: str | None = None,
) -> tuple[str, str, dict[str, Any] | None]:
    dtype = _device_type_text(device_type)
    action_norm = action.casefold().strip()

    if "lock" in dtype:
        if action_norm in {"lock", "on"}:
            return "lock", "default", None
        if action_norm in {"unlock", "off"}:
            return "unlock", "default", None
        return (
            "",
            "",
            {
                "code": "unsupported_device",
                "message": _(
                    "err.unsupported_device",
                    default="The selected device type does not support the requested action.",
                ),
            },
        )

    if "curtain" in dtype or "blind" in dtype:
        if action_norm == "open":
            return "open", "default", None
        if action_norm == "close":
            return "close", "default", None
        if action_norm == "set_value":
            if value is None:
                return (
                    "",
                    "",
                    {
                        "code": "invalid_argument",
                        "message": _(
                            "err.value_required",
                            default="The value field is required for set_value.",
                        ),
                    },
                )
            if value < 0 or value > 100:
                return (
                    "",
                    "",
                    {
                        "code": "invalid_argument",
                        "message": _(
                            "err.invalid_value_range",
                            default="The value field must be between 0 and 100.",
                        ),
                    },
                )
            return "setPosition", str(int(value)), None
        return (
            "",
            "",
            {
                "code": "unsupported_device",
                "message": _(
                    "err.unsupported_device",
                    default="The selected device type does not support the requested action.",
                ),
            },
        )

    if "plug" in dtype or "bot" in dtype:
        if action_norm == "on":
            return "turnOn", "default", None
        if action_norm == "off":
            return "turnOff", "default", None
        return (
            "",
            "",
            {
                "code": "unsupported_device",
                "message": _(
                    "err.unsupported_device",
                    default="The selected device type does not support the requested action.",
                ),
            },
        )

    if "infrared" in dtype or "remote" in dtype:
        raw_remote_type = str(remote_type or "").casefold()
        if action_norm == "on":
            return "turnOn", "default", None
        if action_norm == "off":
            return "turnOff", "default", None
        if action_norm == "brightness_up":
            return "brightnessUp", "default", None
        if action_norm == "brightness_down":
            return "brightnessDown", "default", None
        if action_norm == "set_value" and raw_remote_type in ("air conditioner",):
            if value is None:
                return (
                    "",
                    "",
                    {
                        "code": "invalid_argument",
                        "message": _(
                            "err.value_required",
                            default="The value field is required for set_value.",
                        ),
                    },
                )
            _mode_map = {"auto": "1", "cool": "2", "dry": "3", "fan": "4", "heat": "5"}
            _fan_map = {"auto": "1", "low": "2", "medium": "3", "high": "4"}
            m = _mode_map.get(mode or "", "")
            f = _fan_map.get(fan_speed or "", "")
            clamped = max(16, min(30, value))
            return "setAll", f"{clamped},{m},{f},", None
        return (
            "",
            "",
            {
                "code": "unsupported_device",
                "message": _(
                    "err.unsupported_device",
                    default="The selected infrared remote device type does not support the requested action.",
                ),
            },
        )

    return (
        "",
        "",
        {
            "code": "unsupported_device",
            "message": _(
                "err.unsupported_device",
                default="The selected device type does not support the requested action.",
            ),
        },
    )


def _status_path(device_id: str) -> str:
    return f"/devices/{device_id}/status"


def _command_path(device_id: str) -> str:
    return f"/devices/{device_id}/commands"


def _send_command(
    *,
    device_id: str,
    command: str,
    parameter: str,
    timeout: int,
) -> dict[str, Any]:
    body = {
        "command": command,
        "parameter": parameter,
        "commandType": "command",
    }
    return _request_json(
        _command_path(device_id), method="POST", body=body, timeout=timeout
    )


def _fetch_status(device_id: str, timeout: int) -> dict[str, Any]:
    return _request_json(_status_path(device_id), method="GET", timeout=timeout)


def _format_status_text(status: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if status.get("power") is not None:
        lines.append(f"Power: {status.get('power')}")
    if status.get("mode") is not None:
        lines.append(f"Mode: {status.get('mode')}")
    if status.get("position") is not None:
        lines.append(f"Position: {status.get('position')}")
    if status.get("temperature") is not None:
        lines.append(f"Temperature: {status.get('temperature')}")
    if status.get("humidity") is not None:
        lines.append(f"Humidity: {status.get('humidity')}")
    if status.get("battery") is not None:
        lines.append(f"Battery: {status.get('battery')}")
    if status.get("lock_state") is not None:
        lines.append(f"Lock state: {status.get('lock_state')}")
    if status.get("child_lock") is not None:
        lines.append(f"Child lock: {status.get('child_lock')}")
    return lines


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    device = result.get("device", {}) or {}
    status = result.get("status", {}) or {}
    command = result.get("command", {}) or {}
    lines = [
        _(
            "msg.summary",
            default="SwitchBot Cloud control completed: {action} on {device_name} ({device_id}).",
            action=command.get("action") or "(unknown)",
            device_name=device.get("devname") or "(unknown)",
            device_id=device.get("dev") or "(unknown)",
        ),
        f"Device type: {device.get('device_type') or '-'}",
        f"Command: {command.get('command') or '-'}",
        f"Parameter: {command.get('parameter') or '-'}",
        f"Online: {device.get('online')}",
    ]
    lines.extend(_format_status_text(status))
    lines.append(f"Elapsed ms: {result.get('elapsed_ms')}")
    return "\n".join(lines)


def _build_device_list(devices_data: dict[str, Any]) -> list[dict[str, Any]]:
    body = _extract_body(devices_data)
    sections = _device_sections(body)
    items: list[dict[str, Any]] = []
    for source, devices in sections:
        for item in devices:
            items.append(_normalize_device_item(item, source))
    return items


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    device_id = args.get("dev")
    device_name = args.get("devname")
    action = str(args.get("action") or "").strip()
    raw_value = args.get("value")

    try:
        timeout = int(args.get("timeout", 15))
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_numeric",
                    default="Timeout must be an integer.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    if timeout <= 0:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_range",
                    default="Timeout must be greater than 0.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    try:
        value = None if raw_value is None else int(raw_value)
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_value_type",
                    default="The value field must be an integer.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    started = time.perf_counter()
    try:
        devices_resp = _request_json("/devices", method="GET", timeout=timeout)
        if not devices_resp.get("ok"):
            payload = devices_resp
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        items = _build_device_list(devices_resp["data"])
        device, err = _find_device(
            items,
            str(device_id) if device_id else None,
            str(device_name) if device_name else None,
        )
        if err is not None or device is None:
            payload = {
                "ok": False,
                "error": err or {"code": "not_found", "message": "Not found."},
            }
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        command, parameter, build_err = _action_for_device(
            device_type=device.get("device_type"),
            action=action,
            value=value,
            remote_type=device.get("raw", {}).get("remoteType"),
            mode=args.get("mode"),
            fan_speed=args.get("fan"),
        )
        if build_err is not None or not command:
            payload = {
                "ok": False,
                "error": build_err
                or {"code": "invalid_argument", "message": "Invalid action."},
            }
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        command_resp = _send_command(
            device_id=str(device.get("dev") or ""),
            command=command,
            parameter=parameter,
            timeout=timeout,
        )
        if not command_resp.get("ok"):
            payload = command_resp
            return (
                json.dumps(payload, ensure_ascii=False, indent=2)
                if output_format == "text"
                else json.dumps(payload, ensure_ascii=False)
            )

        status_resp = _fetch_status(str(device.get("dev") or ""), timeout=timeout)
        status_item: dict[str, Any] = {}
        status_raw: dict[str, Any] | None = None
        if status_resp.get("ok"):
            status_raw = _extract_body(status_resp["data"])
            if isinstance(status_raw, dict):
                status_item = _normalize_status_item(status_raw)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "ok": True,
            "device": {
                "dev": device.get("dev"),
                "devname": device.get("devname"),
                "device_type": device.get("device_type"),
                "hub_id": device.get("hub_id"),
                "room_id": device.get("room_id"),
                "model": device.get("model"),
                "firmware": device.get("firmware"),
                "online": device.get("online"),
                "battery": device.get("battery"),
                "reachable": True,
                "last_updated": device.get("last_updated"),
                "source": device.get("source"),
            },
            "status": {
                **status_item,
                "action": action,
                "command": command,
                "parameter": parameter,
                "command_response": command_resp.get("data"),
                "status_response": (
                    status_resp.get("data") if status_resp.get("ok") else None
                ),
            },
            "command": {
                "action": action,
                "command": command,
                "parameter": parameter,
                "device_type": device.get("device_type"),
            },
            "elapsed_ms": elapsed_ms,
            "last_updated": _now_iso(),
            "account": {
                "source": "env:UAGENT_SWITCHBOT_TOKEN/UAGENT_SWITCHBOT_SECRET",
                "authenticated": True,
            },
            "raw": {
                "device": device.get("raw"),
                "command": command_resp.get("data"),
                "status": status_resp.get("data") if status_resp.get("ok") else None,
            },
        }
        if output_format == "text":
            return _format_text(result)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        err_msg = str(exc)
        payload = {
            "ok": False,
            "error": {
                "code": "request_failed",
                "message": _(
                    "err.operation_failed",
                    default="Error during SwitchBot Cloud control: {err_msg}",
                    err_msg=err_msg,
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
