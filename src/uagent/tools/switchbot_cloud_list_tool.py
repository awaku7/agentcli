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
STATUS_LABEL = "tool:switchbot_cloud_list"

_API_BASE = "https://api.switch-bot.com/v1.1"

TOOL_SPEC: dict[str, Any] = {
    "tool_level": 0,
    "tool_genre": "iot",
    "type": "function",
    "function": {
        "name": "switchbot_cloud_list",
        "description": _(
            "tool.description",
            default=("List SwitchBot Cloud devices for the configured account."),
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "output_format": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.output_format.description",
                        default="Output format: JSON or human-readable text.",
                    ),
                }
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


def _request_json(path: str) -> dict[str, Any]:
    token, secret = _get_credentials()
    if not token or not secret:
        return {
            "ok": False,
            "error": {
                "code": "config_missing",
                "message": (
                    "SwitchBot Cloud credentials are missing. Set UAGENT_SWITCHBOT_TOKEN and UAGENT_SWITCHBOT_SECRET."
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
                "message": "SwitchBot Cloud returned an unexpected payload.",
            },
        }
    return {"ok": True, "data": data}


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


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return f"Error: {error.get('message', 'unknown error')}"

    lines = [
        f"SwitchBot Cloud devices: {result.get('count', 0)}",
        f"Fetched at: {result.get('fetched_at', '')}",
    ]
    for item in result.get("items", []):
        lines.append(
            "- {name} [{dtype}] id={did} hub={hub} online={online}".format(
                name=item.get("device_name") or "(unknown)",
                dtype=item.get("device_type") or "(unknown)",
                did=item.get("device_id") or "(unknown)",
                hub=item.get("hub_id") or "-",
                online=item.get("online"),
            )
        )
    return "\n".join(lines)


def run_tool(args: dict[str, Any]) -> str:
    output_format = (args.get("output_format") or "json").lower()
    response = _request_json("/devices")
    if not response.get("ok"):
        payload = response
        return (
            json.dumps(payload, ensure_ascii=False, indent=2)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

    data = response["data"]
    body = data.get("body") if isinstance(data.get("body"), dict) else {}
    sections = _device_sections(body)
    items: list[dict[str, Any]] = []
    for source, devices in sections:
        for item in devices:
            items.append(_normalize_device_item(item, source))

    result = {
        "ok": True,
        "count": len(items),
        "items": items,
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
