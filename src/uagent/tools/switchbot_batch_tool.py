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
STATUS_LABEL = "tool:switchbot_batch"

_API_BASE = "https://api.switch-bot.com/v1.1"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "switchbot_batch",
        "description": _(
            "tool.description",
            default="Execute multiple SwitchBot Cloud commands in sequence.",
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": _(
                                    "param.commands.items.device_id.description",
                                    default="Device ID.",
                                ),
                            },
                            "device_name": {
                                "type": "string",
                                "description": _(
                                    "param.commands.items.device_name.description",
                                    default="SwitchBot device name.",
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
                                    "param.commands.items.action.description",
                                    default="Control action.",
                                ),
                            },
                            "value": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": _(
                                    "param.commands.items.value.description",
                                    default="Value (0-100).",
                                ),
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["auto", "cool", "dry", "fan", "heat"],
                                "description": _(
                                    "param.commands.items.mode.description",
                                    default="AC mode: auto/cool/dry/fan/heat.",
                                ),
                            },
                            "fan_speed": {
                                "type": "string",
                                "enum": ["auto", "low", "medium", "high"],
                                "description": _(
                                    "param.commands.items.fan_speed.description",
                                    default="AC fan: auto/low/medium/high.",
                                ),
                            },
                        },
                        "required": ["action"],
                        "additionalProperties": False,
                    },
                    "description": _(
                        "param.commands.description",
                        default="Commands to execute.",
                    ),
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.output_format.description",
                        default="Format: json or text.",
                    ),
                },
            },
            "required": ["commands"],
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
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
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
                        "SwitchBot Cloud credentials are missing."
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
        body_text_err = (
            exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        )
        try:
            detail = json.loads(body_text_err) if body_text_err else {}
        except Exception:
            detail = {"message": body_text_err or str(exc)}
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


# --- device listing and lookup ---

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
        "device_id": item.get("deviceId") or item.get("device_id"),
        "device_name": item.get("deviceName") or item.get("device_name"),
        "device_type": item.get("deviceType") or item.get("device_type") or source,
        "hub_id": item.get("hubDeviceId") or item.get("hub_id"),
        "remote_type": item.get("remoteType"),
        "raw": item,
    }


def _fetch_all_devices(timeout: int = 15) -> list[dict[str, Any]]:
    resp = _request_json("/devices", method="GET", timeout=timeout)
    if not resp.get("ok"):
        return []
    data = resp["data"]
    body = data.get("body") if isinstance(data.get("body"), dict) else {}
    sections = _device_sections(body)
    items: list[dict[str, Any]] = []
    for source, devices in sections:
        for item in devices:
            items.append(_normalize_device_item(item, source))
    return items


# --- command building (mirrors switchbot_cloud_control logic) ---

_AC_MODE_MAP = {"auto": "1", "cool": "2", "dry": "3", "fan": "4", "heat": "5"}
_AC_FAN_MAP = {"auto": "1", "low": "2", "medium": "3", "high": "4"}


def _resolve_command(device: dict[str, Any], cmd: dict[str, Any]) -> dict[str, Any]:
    """Resolve (command, parameter) from device info and command dict."""
    dtype = str(device.get("device_type") or "").casefold()
    action = str(cmd.get("action") or "").casefold().strip()

    # infrared remote devices
    if "infrared" in dtype or "remote" in dtype:
        if action == "on":
            return {"command": "turnOn", "parameter": "default", "action": action}
        if action == "off":
            return {"command": "turnOff", "parameter": "default", "action": action}
        if action == "brightness_up":
            return {"command": "brightnessUp", "parameter": "default", "action": action}
        if action == "brightness_down":
            return {"command": "brightnessDown", "parameter": "default", "action": action}
        if action == "set_value":
            raw_remote_type = str(device.get("remote_type") or "").casefold()
            if raw_remote_type in ("air conditioner",):
                value = cmd.get("value")
                if value is None:
                    return {"error": "value is required for air conditioner set_value"}
                clamped = max(16, min(30, int(value)))
                mode = cmd.get("mode")
                fan_speed = cmd.get("fan_speed")
                m = _AC_MODE_MAP.get(mode or "", "")
                f = _AC_FAN_MAP.get(fan_speed or "", "")
                return {"command": "setAll", "parameter": f"{clamped},{m},{f},", "action": action}
            return {"error": f"Unsupported remote type for set_value: {raw_remote_type}"}
        return {"error": f"Unsupported action for infrared device: {action}"}

    # lock devices
    if "lock" in dtype:
        if action in ("lock", "on"):
            return {"command": "lock", "parameter": "default", "action": action}
        if action in ("unlock", "off"):
            return {"command": "unlock", "parameter": "default", "action": action}
        return {"error": f"Unsupported action for lock device: {action}"}

    # curtain / blind
    if "curtain" in dtype or "blind" in dtype:
        if action == "open":
            return {"command": "open", "parameter": "default", "action": action}
        if action == "close":
            return {"command": "close", "parameter": "default", "action": action}
        if action == "set_value":
            value = cmd.get("value")
            if value is None:
                return {"error": "value is required for set_value on curtain/blind"}
            return {"command": "setPosition", "parameter": str(int(value)), "action": action}
        return {"error": f"Unsupported action for curtain/blind: {action}"}

    # plug / bot
    if "plug" in dtype or "bot" in dtype:
        if action == "on":
            return {"command": "turnOn", "parameter": "default", "action": action}
        if action == "off":
            return {"command": "turnOff", "parameter": "default", "action": action}
        return {"error": f"Unsupported action for plug/bot: {action}"}

    return {"error": f"Unknown device type or unsupported action: {dtype}/{action}"}


def _send_command(
    device_id: str, command: str, parameter: str, timeout: int
) -> dict[str, Any]:
    body = {"command": command, "parameter": parameter, "commandType": "command"}
    return _request_json(
        f"/devices/{device_id}/commands", method="POST", body=body, timeout=timeout
    )


def _format_result_text(result: dict[str, Any]) -> str:
    lines = [
        f"Batch completed: {result.get('total', 0)} command(s), "
        f"{result.get('succeeded', 0)} succeeded, "
        f"{result.get('failed', 0)} failed",
    ]
    for i, step in enumerate(result.get("steps", []), 1):
        status = "OK" if step.get("ok") else "FAIL"
        label = step.get("label", f"cmd#{i}")
        lines.append(f"  [{status}] {label}")
        if step.get("error"):
            lines.append(f"         Error: {step['error']}")
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("output_format") or "json").lower()
    commands = args.get("commands", [])

    if not commands or not isinstance(commands, list):
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.commands_required",
                    default="The commands field must be a non-empty array.",
                ),
            },
        }
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    started = time.perf_counter()

    # Fetch device list once for resolution
    devices = _fetch_all_devices()
    device_index: dict[str, dict[str, Any]] = {}
    for dev in devices:
        did = dev.get("device_id")
        dname = dev.get("device_name")
        if did:
            device_index[did.casefold()] = dev
        if dname:
            device_index[dname.casefold()] = dev

    def _find_device(cmd: dict[str, Any]) -> dict[str, Any] | None:
        did = cmd.get("device_id")
        dname = cmd.get("device_name")
        if did:
            key = did.casefold()
            if key in device_index:
                return device_index[key]
        if dname:
            key = dname.casefold()
            if key in device_index:
                return device_index[key]
            # partial match
            for dev_key, dev in device_index.items():
                if key in dev_key:
                    return dev
        return None

    steps: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    for cmd in commands:
        device = _find_device(cmd)
        if device is None:
            steps.append({
                "ok": False,
                "label": f"{cmd.get('device_id') or cmd.get('device_name') or '?'}",
                "error": "Device not found",
            })
            failed += 1
            continue

        resolved = _resolve_command(device, cmd)
        if "error" in resolved:
            steps.append({
                "ok": False,
                "label": f"{device.get('device_name')}/{cmd.get('action')}",
                "error": resolved["error"],
            })
            failed += 1
            continue

        resp = _send_command(
            device_id=str(device.get("device_id") or ""),
            command=resolved["command"],
            parameter=resolved["parameter"],
            timeout=15,
        )
        if resp.get("ok"):
            succeeded += 1
            steps.append({
                "ok": True,
                "label": f"{device.get('device_name')}/{cmd.get('action')}",
                "command": resolved["command"],
                "parameter": resolved["parameter"],
                "response": resp["data"],
            })
        else:
            failed += 1
            steps.append({
                "ok": False,
                "label": f"{device.get('device_name')}/{cmd.get('action')}",
                "error": resp.get("error", {}).get("message", "unknown"),
            })

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "ok": True,
        "total": len(commands),
        "succeeded": succeeded,
        "failed": failed,
        "steps": steps,
        "elapsed_ms": elapsed_ms,
    }

    if output_format == "text":
        return _format_result_text(result)
    return json.dumps(result, ensure_ascii=False)
