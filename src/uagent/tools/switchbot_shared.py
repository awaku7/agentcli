"""SwitchBot shared resources: background status polling for subscription.

SwitchBot Cloud API has no webhook, so we poll device status
at a configurable interval and queue changes to SchedulerStore.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_API_BASE = "https://api.switch-bot.com/v1.1"
_POLLERS: dict[str, dict[str, Any]] = {}
_POLLERS_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()


def _get_credentials() -> tuple[str | None, str | None]:
    token = os.getenv("UAGENT_SWITCHBOT_TOKEN")
    secret = os.getenv("UAGENT_SWITCHBOT_SECRET")
    return token, secret


def _make_sign(token: str, secret: str) -> dict[str, str]:
    t = int(round(time.time() * 1000))
    nonce = str(uuid.uuid4())
    data = token + str(t) + nonce
    sign = base64.b64encode(
        hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "sign": sign,
        "t": str(t),
        "nonce": nonce,
    }


def _fetch_device_status(device_id: str) -> dict[str, Any] | None:
    """Fetch status for one device from SwitchBot Cloud API."""
    token, secret = _get_credentials()
    if not token or not secret:
        return None
    headers = _make_sign(token, secret)
    url = f"{_API_BASE}/devices/{device_id}/status"
    try:
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
        if data.get("statusCode") == 100:
            return data.get("body", {})
    except Exception:
        pass
    return None


def _fetch_device_list() -> list[dict[str, Any]]:
    """Fetch all registered devices from SwitchBot Cloud API."""
    token, secret = _get_credentials()
    if not token or not secret:
        return []
    headers = _make_sign(token, secret)
    try:
        req = Request(f"{_API_BASE}/devices", headers=headers, method="GET")
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
        if data.get("statusCode") == 100:
            body_data = data.get("body", {})
            devices: list[dict] = []
            for cat in ("deviceList", "infraredRemoteList"):
                devices.extend(body_data.get(cat) or [])
            return devices
    except Exception:
        pass
    return []


def _poller_loop(sub_id: str, device_id: str, interval: int) -> None:
    """Background thread: poll device status at interval."""
    last_status: str | None = None

    while not _STOP_EVENT.is_set():
        with _POLLERS_LOCK:
            info = _POLLERS.get(sub_id)
            if info is None or not info.get("enabled", True):
                return

        status = _fetch_device_status(device_id)
        if status is None:
            time.sleep(interval)
            continue

        current = json.dumps(status, sort_keys=True, ensure_ascii=False)
        if last_status is not None and current != last_status:
            # Change detected
            label = info.get("label", device_id) if info else device_id
            prompt = info.get("on_change_prompt", f"SwitchBot {label} state changed")

            from ..scheduler import SchedulerStore, ScheduleItem, format_iso_datetime, utc_now

            item = ScheduleItem(
                id=str(uuid.uuid4()),
                type="once",
                at=format_iso_datetime(utc_now() + timedelta(seconds=1)),
                message=f"[SwitchBot] {label}: {current}",
                llm_prompt=prompt,
                interval_sec=0,
                enabled=True,
            )
            SchedulerStore().add_item(item)

        last_status = current

        # Wait for next poll interval
        for _ in range(interval * 2):  # 0.5s granularity
            if _STOP_EVENT.is_set():
                return
            time.sleep(0.5)


def subscribe(
    device_id: str,
    interval: int = 60,
    label: str = "",
    on_change_prompt: str = "",
) -> dict[str, Any]:
    """Subscribe to SwitchBot device status changes via polling."""
    sub_id = f"switchbot_{device_id}_{int(time.time())}"

    info: dict[str, Any] = {
        "device_id": device_id,
        "interval": interval,
        "label": label or device_id,
        "on_change_prompt": on_change_prompt,
        "enabled": True,
    }
    with _POLLERS_LOCK:
        _POLLERS[sub_id] = info

    thread = threading.Thread(
        target=_poller_loop,
        args=(sub_id, device_id, interval),
        daemon=True,
        name=f"switchbot-poll-{device_id[:8]}",
    )
    thread.start()

    return {"ok": True, "subscription_id": sub_id, "subscription": info}


def unsubscribe(subscription_id: str) -> dict[str, Any]:
    """Unsubscribe from SwitchBot polling."""
    with _POLLERS_LOCK:
        if subscription_id not in _POLLERS:
            return {"ok": False, "error": f"subscription_id '{subscription_id}' not found"}
        info = _POLLERS.pop(subscription_id)
        info["enabled"] = False
    return {"ok": True, "subscription_id": subscription_id, "subscription": info}


def list_subscriptions() -> dict[str, Any]:
    """List all active SwitchBot subscriptions."""
    with _POLLERS_LOCK:
        subs = [{"subscription_id": k, **v} for k, v in _POLLERS.items()]
    return {"ok": True, "count": len(subs), "subscriptions": subs}


def stop() -> None:
    """Stop all SwitchBot pollers."""
    _STOP_EVENT.set()
    with _POLLERS_LOCK:
        _POLLERS.clear()
