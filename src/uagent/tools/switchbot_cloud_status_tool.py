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
from urllib.parse import quote
from urllib.request import Request, urlopen

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:switchbot_cloud_status"

_API_BASE = "https://api.switch-bot.com/v1.1"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "switchbot_cloud_status",
        "description": _(
            "tool.description",
            default=(
                "Get the status of one SwitchBot Cloud device from the configured account."
            ),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": _(
                        "param.device_id.description",
                        default="Device ID (preferred).",
                    ),
                },
                "device_name": {
                    "type": "string",
                    "description": _(
                        "param.device_name.description",
                        default="Device name (fallback).",
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


def _request_json(path: str) -> dict[str, Any]:
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

    url = f"{_API_BASE}{path}"
    headers = _build_auth_headers(token, secret)
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw or "{}")
    except HTTPError as exc:
        body = (
            exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        )
        try:
            detail = json.loads(body) if body else {}
        except Exception:
            detail = {"message": body or str(exc)}
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

    if not isinstance(data, dict):
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
    return {"ok": True, "data": data}


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
        "device_id": item.get("deviceId") or item.get("device_id"),
        "device_name": item.get("deviceName") or item.get("device_name"),
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
        "fan_speed": item.get("fanSpeed") or item.get("fan_speed"),
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
            candidate = str(item.get("device_id") or "").casefold()
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
    exact = [
        item
        for item in items
        if str(item.get("device_name") or "").casefold() == device_name.casefold()
    ]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, {
            "code": "ambiguous_target",
            "message": _(
                "err.ambiguous_target",
                default="Multiple SwitchBot devices matched the provided device_name.",
                device_name=device_name,
            ),
        }

    partial = [
        item
        for item in items
        if device_name.casefold() in str(item.get("device_name") or "").casefold()
    ]
    if len(partial) == 1:
        return partial[0], None
    if len(partial) > 1:
        return None, {
            "code": "ambiguous_target",
            "message": _(
                "err.ambiguous_target",
                default="Multiple SwitchBot devices matched the provided device_name.",
                device_name=device_name,
            ),
        }
    return None, {
        "code": "not_found",
        "message": _(
            "err.not_found",
            default="No SwitchBot device matched the provided device_name.",
            device_name=device_name,
        ),
    }


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        code = error.get("code", "error")
        message = error.get("message", "unknown error")
        return f"Error [{code}]: {message}"

    device = result.get("device") or {}
    status = result.get("status") or {}
    lines = [
        _(
            "msg.summary",
            default="SwitchBot Cloud status fetched: {device_name} ({device_id}).",
            device_name=device.get("device_name") or "(unknown)",
            device_id=device.get("device_id") or "(unknown)",
        ),
        f"Type: {device.get('device_type') or '(unknown)'}",
        f"Online: {device.get('online')}",
        f"Battery: {device.get('battery')}",
        f"Power: {status.get('power')}",
        f"Mode: {status.get('mode')}",
        f"Temperature: {status.get('temperature')}",
        f"Humidity: {status.get('humidity')}",
        f"Position: {status.get('position')}",
        f"Lock state: {status.get('lock_state')}",
        f"Fetched at: {result.get('fetched_at', '')}",
    ]
    return "\n".join(lines)


def _fetch_devices() -> dict[str, Any]:
    response = _request_json("/devices")
    if not response.get("ok"):
        return response

    data = response["data"]
    body = _extract_body(data)
    sections = _device_sections(body)
    items: list[dict[str, Any]] = []
    for source, devices in sections:
        for item in devices:
            items.append(_normalize_device_item(item, source))

    return {
        "ok": True,
        "items": items,
        "raw": data,
    }


def _fetch_device_status(device_id: str) -> dict[str, Any]:
    encoded = quote(device_id, safe="")
    return _request_json(f"/devices/{encoded}/status")


def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("output_format") or "json").lower()
    device_id = args.get("device_id")
    device_name = args.get("device_name")

    devices_response = _fetch_devices()
    if not devices_response.get("ok"):
        payload = devices_response
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    items = devices_response.get("items", [])
    selected, error = _find_device(items, device_id, device_name)
    if error:
        payload = {"ok": False, "error": error}
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
    assert selected is not None

    status_response = _fetch_device_status(str(selected.get("device_id") or ""))
    if not status_response.get("ok"):
        payload = status_response
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    data = status_response["data"]
    body = _extract_body(data)
    status = _normalize_status_item(body)
    capabilities = sorted(k for k in body.keys() if k != "raw")

    result = {
        "ok": True,
        "device": selected,
        "status": status,
        "capabilities": capabilities,
        "account": {
            "source": "env:UAGENT_SWITCHBOT_TOKEN/UAGENT_SWITCHBOT_SECRET",
            "authenticated": True,
        },
        "fetched_at": _now_iso(),
        "raw": {
            "statusCode": data.get("statusCode"),
            "message": data.get("message"),
        },
    }
    if output_format == "text":
        return _format_text(result)
    return json.dumps(result, ensure_ascii=False)
