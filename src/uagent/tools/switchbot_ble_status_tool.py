from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:switchbot_ble_status"
_SWITCHBOT_COMPANY_IDS = {0x0969, 0x02E5, 0x0059}
_SWITCHBOT_SERVICE_UUIDS = {
    "0000fd3d-0000-1000-8000-00805f9b34fb",
    "00000d00-0000-1000-8000-00805f9b34fb",
    "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
}
_BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
# Official SwitchBotAPI-BLE device type codes (service data byte0 bit[6:0])
_DEVICE_TYPES = {
    0x48: "Bot",
    0x42: "WoButton",
    0x4C: "Hub",
    0x6C: "Hub",
    0x50: "Hub Plus",
    0x70: "Hub Plus",
    0x46: "Fan",
    0x66: "Fan",
    0x74: "Meter",
    0x54: "Meter",
    0x4D: "Hub Mini",
    0x6D: "Hub Mini",
    0x63: "Curtain",
    0x43: "Curtain",
    0x7B: "Curtain 3",
    0x5B: "Curtain 3",
    0x73: "Motion Sensor",
    0x53: "Motion Sensor",
    0x64: "Contact Sensor",
    0x44: "Contact Sensor",
    0x75: "Color Bulb",
    0x72: "LED Strip Light",
    0x6F: "Smart Lock",
    0x67: "Plug Mini",
    0x69: "Meter Plus",
    0x77: "Outdoor Meter",
    0x65: "Humidifier",
}
_METER_DEVICE_TYPES = {
    0x54: "Meter",
    0x74: "Meter",
    0x69: "Meter Plus",
    0x77: "Outdoor Meter",
}
_CURTAIN_DEVICE_TYPES = {0x63, 0x43, 0x7B, 0x5B}
_MOTION_DEVICE_TYPES = {0x73, 0x53}
_CONTACT_DEVICE_TYPES = {0x64, 0x44}
_BOT_DEVICE_TYPES = {0x48, 0x42}
_HUB_DEVICE_TYPES = {0x4C, 0x6C, 0x50, 0x70, 0x4D, 0x6D}
_LOCK_DEVICE_TYPES = {0x6F}
_PLUG_DEVICE_TYPES = {0x67}
_BULB_DEVICE_TYPES = {0x75}
_STRIP_DEVICE_TYPES = {0x72}

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "iot",
    "tool_level": 1,
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "switchbot_ble_status",
        "description": _(
            "tool.description",
            default=(
                "Read the status of a nearby SwitchBot BLE device and return a JSON or text summary."
            ),
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "switchbot ble status",
                "switchbot_ble_status",
                "switchbot",
                "nearby",
            ],
        ),
        "x_search_terms_en": [
            "switchbot ble status",
            "switchbot_ble_status",
            "switchbot",
            "nearby",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "interface": {
                    "type": "string",
                    "description": _(
                        "param.interface.description",
                        default=("Optional local BLE adapter/interface name to bind to."),
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "default": 8,
                    "minimum": 1,
                    "description": _(
                        "param.timeout.description",
                        default=("Scan/connect timeout in seconds."),
                    ),
                },
                "retry": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 1,
                    "description": _(
                        "param.retry.description",
                        default=("How many BLE scan rounds to run before connecting."),
                    ),
                },
                "limit": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "description": _(
                        "param.limit.description",
                        default=("Max characteristics (0 = unlimited)."),
                    ),
                },
                "devname": {
                    "type": "string",
                    "description": _(
                        "param.devname.description",
                        default=("Device name filter."),
                    ),
                },
                "mac": {
                    "type": "string",
                    "description": _(
                        "param.mac.description",
                        default="MAC address filter.",
                    ),
                },
                "service_uuid": {
                    "type": "string",
                    "description": _(
                        "param.service_uuid.description",
                        default=("Optional GATT service UUID filter."),
                    ),
                },
                "fmt": {
                    "type": "string",
                    "enum": ["json", "text"],
                    "default": "json",
                    "description": _(
                        "param.fmt.description",
                        default="Output as json or text.",
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
}

def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _hex_to_bytes(value: Any) -> bytes | None:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if not isinstance(value, str):
        return None
    text = value.strip().lower().replace(":", "").replace(" ", "")
    if text.startswith("0x"):
        text = text[2:]
    if not text or len(text) % 2:
        return None
    try:
        return bytes.fromhex(text)
    except Exception:
        return None


def _normalize_manufacturer_data(data: dict[Any, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for company_id, payload in (data or {}).items():
        raw = _hex_to_bytes(payload)
        if raw is None:
            continue
        normalized[str(company_id)] = raw.hex()
    return normalized


def _normalize_service_data(data: dict[Any, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for uuid, payload in (data or {}).items():
        raw = _hex_to_bytes(payload)
        if raw is None:
            continue
        normalized[str(uuid).casefold()] = raw.hex()
    return normalized

def _looks_like_switchbot(
    name: str | None,
    manufacturer_data: dict[str, str],
    service_data: dict[str, str] | None = None,
    service_uuids: list[str] | None = None,
) -> bool:
    if name and "switchbot" in name.casefold():
        return True
    for key in manufacturer_data:
        try:
            if int(key) in _SWITCHBOT_COMPANY_IDS:
                return True
        except Exception:
            if str(key) in {str(v) for v in _SWITCHBOT_COMPANY_IDS}:
                return True
    for uuid in service_data or {}:
        if str(uuid).casefold() in _SWITCHBOT_SERVICE_UUIDS:
            return True
    for uuid in service_uuids or []:
        if str(uuid).casefold() in _SWITCHBOT_SERVICE_UUIDS:
            return True
    return False


def _matches_filters(
    *,
    address: str,
    name: str | None,
    service_uuids: list[str],
    device_name: str | None,
    mac_address: str | None,
    service_uuid: str | None,
) -> bool:
    if mac_address and address.casefold() != mac_address.casefold():
        return False
    if device_name:
        needle = device_name.casefold()
        haystack = (name or "").casefold()
        if needle not in haystack:
            return False
    if service_uuid:
        target = service_uuid.casefold()
        if target not in {u.casefold() for u in service_uuids}:
            return False
    return True

def _pick_service_data_bytes(service_data: dict[str, str]) -> bytes | None:
    preferred = [
        "0000fd3d-0000-1000-8000-00805f9b34fb",
        "00000d00-0000-1000-8000-00805f9b34fb",
        "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
    ]
    for uuid in preferred:
        if uuid in service_data:
            return _hex_to_bytes(service_data[uuid])
    for uuid, payload in service_data.items():
        raw = _hex_to_bytes(payload)
        if raw:
            return raw
    return None


def _pick_manufacturer_data_bytes(manufacturer_data: dict[str, str]) -> bytes | None:
    preferred = ["2409", "741", "89"]
    for key in preferred:
        if key in manufacturer_data:
            return _hex_to_bytes(manufacturer_data[key])
    for key, payload in manufacturer_data.items():
        try:
            if int(key) in _SWITCHBOT_COMPANY_IDS:
                return _hex_to_bytes(payload)
        except Exception:
            continue
    for payload in manufacturer_data.values():
        raw = _hex_to_bytes(payload)
        if raw:
            return raw
    return None

def _decode_temp_humidity_bytes(
    temp_data: bytes, battery: int | None = None
) -> dict[str, Any] | None:
    if len(temp_data) < 3:
        return None
    temp_sign = 1 if temp_data[1] & 0b10000000 else -1
    temperature = temp_sign * (
        (temp_data[1] & 0b01111111) + ((temp_data[0] & 0b00001111) / 10.0)
    )
    humidity = temp_data[2] & 0b01111111
    fahrenheit = bool(temp_data[2] & 0b10000000)
    if temperature == 0 and humidity == 0 and (battery in (None, 0)):
        return None
    if humidity > 100:
        return None
    return {
        "temperature": round(temperature, 1),
        "humidity": int(humidity),
        "fahrenheit": fahrenheit,
        "battery": battery,
    }


def _common_status(
    *,
    model: str | None,
    device_type_code: int | None,
    battery: int | None,
    source: str,
    **fields: Any,
) -> dict[str, Any]:
    return {
        **fields,
        "model": model,
        "device_type_code": device_type_code,
        "battery": battery,
        "source": source,
        "connected": False,
    }


def _decode_meter_payload(
    *,
    svc: bytes | None,
    mfr: bytes | None,
    device_type_code: int | None,
    model: str | None,
) -> dict[str, Any] | None:
    temp_data: bytes | None = None
    battery: int | None = None
    source: str | None = None
    if svc and len(svc) >= 6:
        battery = svc[2] & 0b01111111
        temp_data = svc[3:6]
        source = "service_data"
    elif mfr and len(mfr) >= 11:
        temp_data = mfr[8:11]
        source = "manufacturer_data"
        if svc and len(svc) >= 3:
            battery = svc[2] & 0b01111111
    elif mfr and len(mfr) >= 13:
        temp_data = bytes([(mfr[10] & 0x0F), mfr[11], mfr[12]])
        source = "manufacturer_data_outdoor"
        if svc and len(svc) >= 3:
            battery = svc[2] & 0b01111111
    if temp_data is None or source is None:
        return None
    decoded = _decode_temp_humidity_bytes(temp_data, battery)
    if not decoded:
        return None
    return _common_status(
        model=model or "Meter",
        device_type_code=device_type_code,
        battery=decoded.get("battery"),
        source=source,
        temperature=decoded["temperature"],
        humidity=decoded["humidity"],
        fahrenheit=decoded["fahrenheit"],
    )


def _decode_bot_payload(
    *,
    svc: bytes,
    device_type_code: int,
    model: str,
) -> dict[str, Any] | None:
    if len(svc) < 3:
        return None
    status = svc[1]
    battery = svc[2] & 0b01111111
    mode = "on_off" if (status & 0b10000000) else "press"
    # Spec: Bit[6] State 0=on, 1=off
    power = "off" if (status & 0b01000000) else "on"
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="service_data",
        mode=mode,
        power=power,
        is_on=(power == "on"),
    )


def _decode_curtain_payload(
    *,
    svc: bytes,
    device_type_code: int,
    model: str,
) -> dict[str, Any] | None:
    if len(svc) < 4:
        return None
    status = svc[1] if len(svc) > 1 else 0
    battery = svc[2] & 0b01111111 if len(svc) > 2 else None
    motion_pos = svc[3]
    moving = bool(motion_pos & 0b10000000)
    position = motion_pos & 0b01111111
    light_level = None
    device_chain = None
    if len(svc) >= 5:
        light_level = (svc[4] >> 4) & 0x0F
        device_chain = svc[4] & 0x0F
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="service_data",
        calibrated=bool(status & 0b01000000),
        connectable=bool(status & 0b10000000),
        moving=moving,
        position=position,
        light_level=light_level,
        device_chain=device_chain,
    )


def _decode_motion_payload(
    *,
    svc: bytes,
    device_type_code: int,
    model: str,
) -> dict[str, Any] | None:
    if len(svc) < 3:
        return None
    status = svc[1]
    battery = svc[2] & 0b01111111
    motion = bool(status & 0b01000000)
    light_level = None
    sensing_distance = None
    led_enabled = None
    iot_enabled = None
    last_motion_seconds = None
    if len(svc) >= 5:
        last_motion_seconds = ((svc[3] << 8) | svc[4]) & 0xFFFF
    if len(svc) >= 6:
        sensor = svc[5]
        if last_motion_seconds is not None and (sensor & 0b10000000):
            last_motion_seconds += 65536
        led_enabled = bool(sensor & 0b00100000)
        iot_enabled = bool(sensor & 0b00010000)
        dist_code = (sensor >> 2) & 0b11
        sensing_distance = {0: "long", 1: "middle", 2: "short"}.get(dist_code)
        light_code = sensor & 0b11
        light_level = {1: "dark", 2: "bright"}.get(light_code)
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="service_data",
        motion=motion,
        light_level=light_level,
        sensing_distance=sensing_distance,
        led_enabled=led_enabled,
        iot_enabled=iot_enabled,
        last_motion_seconds=last_motion_seconds,
    )


def _decode_contact_payload(
    *,
    svc: bytes,
    device_type_code: int,
    model: str,
) -> dict[str, Any] | None:
    if len(svc) < 4:
        return None
    status = svc[1]
    battery = svc[2] & 0b01111111
    sensor = svc[3]
    motion = bool(status & 0b01000000)
    door_code = (sensor >> 1) & 0b11
    door_state = {0: "closed", 1: "open", 2: "timeout_not_closed"}.get(door_code, "unknown")
    light_level = "light" if (sensor & 0b1) else "dark"
    last_motion_seconds = None
    last_contact_seconds = None
    if len(svc) >= 6:
        last_motion_seconds = ((svc[4] << 8) | svc[5]) & 0xFFFF
        if sensor & 0b10000000:
            last_motion_seconds += 65536
    if len(svc) >= 8:
        last_contact_seconds = ((svc[6] << 8) | svc[7]) & 0xFFFF
        if sensor & 0b01000000:
            last_contact_seconds += 65536
    button_count = None
    entry_count = None
    exit_count = None
    if len(svc) >= 9:
        act = svc[8]
        entry_count = (act >> 6) & 0b11
        exit_count = (act >> 4) & 0b11
        button_count = act & 0b1111
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="service_data",
        motion=motion,
        door_state=door_state,
        open=(door_state == "open"),
        light_level=light_level,
        last_motion_seconds=last_motion_seconds,
        last_contact_seconds=last_contact_seconds,
        button_count=button_count,
        entry_count=entry_count,
        exit_count=exit_count,
    )


def _decode_lock_payload(
    *,
    svc: bytes | None,
    mfr: bytes | None,
    device_type_code: int | None,
    model: str,
) -> dict[str, Any] | None:
    battery = None
    if svc and len(svc) >= 3:
        battery = svc[2] & 0b01111111
        if device_type_code is None:
            device_type_code = svc[0] & 0b01111111
    # Manufacturer payload after company id is stripped by bleak:
    # [0:6]=mac, [6]=seq, [7]=lock info, [8]=double lock, [9]=reserve
    if not mfr or len(mfr) < 8:
        if battery is None:
            return None
        return _common_status(
            model=model,
            device_type_code=device_type_code,
            battery=battery,
            source="service_data",
        )
    lock_info = mfr[7]
    calibrated = bool(lock_info & 0b10000000)
    lock_code = (lock_info >> 4) & 0b111
    lock_state = {
        0: "locked",
        1: "unlocked",
        2: "locking",
        3: "unlocking",
        4: "locking_stop",
        5: "unlocking_stop",
        6: "not_fully_locked",
    }.get(lock_code, "unknown")
    door_open = bool(lock_info & 0b00000100)
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="manufacturer_data" if mfr else "service_data",
        calibrated=calibrated,
        lock_state=lock_state,
        is_locked=(lock_state == "locked"),
        door_open=door_open,
    )


def _decode_plug_payload(
    *,
    mfr: bytes | None,
    svc: bytes | None,
    device_type_code: int | None,
    model: str,
) -> dict[str, Any] | None:
    # Manufacturer: [0:6]=mac, [6]=seq, [7]=state, [8]=flags, [9]=wifi rssi,
    # [10]=overload+power msb, [11]=power lsb
    if not mfr or len(mfr) < 8:
        return None
    power_on = bool(mfr[7] & 0x80)
    delay = bool(mfr[8] & 0x01) if len(mfr) > 8 else None
    timer = bool(mfr[8] & 0x02) if len(mfr) > 8 else None
    wifi_rssi = int(mfr[9]) if len(mfr) > 9 else None
    if wifi_rssi is not None and wifi_rssi > 127:
        wifi_rssi -= 256
    overload = None
    power_w = None
    if len(mfr) >= 12:
        overload = bool(mfr[10] & 0x80)
        power_raw = ((mfr[10] & 0x7F) << 8) | mfr[11]
        # Official docs store power as raw value; pySwitchbot uses /10
        power_w = round(power_raw / 10.0, 1)
    battery = None
    if svc and len(svc) >= 3:
        battery = svc[2] & 0b01111111
        if device_type_code is None:
            device_type_code = svc[0] & 0b01111111
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="manufacturer_data",
        power="on" if power_on else "off",
        is_on=power_on,
        delay=delay,
        timer=timer,
        wifi_rssi=wifi_rssi,
        overload=overload,
        power_w=power_w,
    )


def _decode_bulb_or_strip_payload(
    *,
    mfr: bytes | None,
    svc: bytes | None,
    device_type_code: int | None,
    model: str,
) -> dict[str, Any] | None:
    # Manufacturer: [0:6]=mac, [6]=seq, [7]=power+brightness
    if not mfr or len(mfr) < 8:
        return None
    power_on = bool(mfr[7] & 0x80)
    brightness = mfr[7] & 0x7F
    delay = bool(mfr[8] & 0x80) if len(mfr) > 8 else None
    light_state = None
    if len(mfr) > 8:
        mode_code = mfr[8] & 0x07
        light_state = {1: "white", 2: "color", 3: "dynamic"}.get(mode_code)
    battery = None
    if svc and len(svc) >= 3:
        battery = svc[2] & 0b01111111
        if device_type_code is None:
            device_type_code = svc[0] & 0b01111111
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="manufacturer_data",
        power="on" if power_on else "off",
        is_on=power_on,
        brightness=brightness,
        delay=delay,
        light_state=light_state,
    )


def _decode_hub_payload(
    *,
    svc: bytes,
    device_type_code: int,
    model: str,
) -> dict[str, Any] | None:
    if len(svc) < 1:
        return None
    battery = svc[2] & 0b01111111 if len(svc) >= 3 else None
    return _common_status(
        model=model,
        device_type_code=device_type_code,
        battery=battery,
        source="service_data",
        online=True,
    )


def _decode_switchbot_from_adv(
    *,
    manufacturer_data: dict[str, str],
    service_data: dict[str, str],
) -> dict[str, Any] | None:
    mfr = _pick_manufacturer_data_bytes(manufacturer_data)
    svc = _pick_service_data_bytes(service_data)
    device_type_code: int | None = None
    if svc and len(svc) >= 1:
        device_type_code = svc[0] & 0b01111111
    model = _DEVICE_TYPES.get(device_type_code) if device_type_code is not None else None

    # Prefer type-specific service-data decoders.
    if device_type_code is not None and svc is not None:
        if device_type_code in _METER_DEVICE_TYPES:
            decoded = _decode_meter_payload(
                svc=svc, mfr=mfr, device_type_code=device_type_code, model=model
            )
            if decoded:
                return decoded
        if device_type_code in _BOT_DEVICE_TYPES:
            decoded = _decode_bot_payload(
                svc=svc, device_type_code=device_type_code, model=model or "Bot"
            )
            if decoded:
                return decoded
        if device_type_code in _CURTAIN_DEVICE_TYPES:
            decoded = _decode_curtain_payload(
                svc=svc, device_type_code=device_type_code, model=model or "Curtain"
            )
            if decoded:
                return decoded
        if device_type_code in _MOTION_DEVICE_TYPES:
            decoded = _decode_motion_payload(
                svc=svc, device_type_code=device_type_code, model=model or "Motion Sensor"
            )
            if decoded:
                return decoded
        if device_type_code in _CONTACT_DEVICE_TYPES:
            decoded = _decode_contact_payload(
                svc=svc, device_type_code=device_type_code, model=model or "Contact Sensor"
            )
            if decoded:
                return decoded
        if device_type_code in _LOCK_DEVICE_TYPES:
            decoded = _decode_lock_payload(
                svc=svc, mfr=mfr, device_type_code=device_type_code, model=model or "Smart Lock"
            )
            if decoded:
                return decoded
        if device_type_code in _PLUG_DEVICE_TYPES:
            decoded = _decode_plug_payload(
                mfr=mfr, svc=svc, device_type_code=device_type_code, model=model or "Plug Mini"
            )
            if decoded:
                return decoded
        if device_type_code in _BULB_DEVICE_TYPES or device_type_code in _STRIP_DEVICE_TYPES:
            decoded = _decode_bulb_or_strip_payload(
                mfr=mfr,
                svc=svc,
                device_type_code=device_type_code,
                model=model or ("Color Bulb" if device_type_code in _BULB_DEVICE_TYPES else "LED Strip Light"),
            )
            if decoded:
                return decoded
        if device_type_code in _HUB_DEVICE_TYPES:
            decoded = _decode_hub_payload(
                svc=svc, device_type_code=device_type_code, model=model or "Hub"
            )
            if decoded:
                return decoded

    # Fallbacks when service data type is missing/incomplete.
    meter = _decode_meter_payload(svc=svc, mfr=mfr, device_type_code=device_type_code, model=model)
    if meter:
        return meter
    plug = _decode_plug_payload(
        mfr=mfr, svc=svc, device_type_code=device_type_code, model=model or "Plug Mini"
    )
    if plug:
        return plug
    bulb = _decode_bulb_or_strip_payload(
        mfr=mfr, svc=svc, device_type_code=device_type_code, model=model or "Color Bulb"
    )
    if bulb:
        return bulb
    lock = _decode_lock_payload(
        svc=svc, mfr=mfr, device_type_code=device_type_code, model=model or "Smart Lock"
    )
    if lock:
        return lock

    # Generic battery/model only.
    if svc and len(svc) >= 3 and device_type_code is not None:
        return _common_status(
            model=model or _DEVICE_TYPES.get(device_type_code) or "SwitchBot",
            device_type_code=device_type_code,
            battery=svc[2] & 0b01111111,
            source="service_data",
        )
    return None


def _decode_meter_from_adv(
    *,
    manufacturer_data: dict[str, str],
    service_data: dict[str, str],
) -> dict[str, Any] | None:
    # Backward-compatible alias used by tests and callers.
    return _decode_switchbot_from_adv(
        manufacturer_data=manufacturer_data,
        service_data=service_data,
    )

def _merge_device(current: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    if item.get("rssi") is not None and (
        current.get("rssi") is None or item.get("rssi") > current.get("rssi")
    ):
        current["rssi"] = item.get("rssi")
    current["service_uuids"] = sorted(
        {*(current.get("service_uuids") or []), *(item.get("service_uuids") or [])}
    )
    current["manufacturer_data"] = {
        **(current.get("manufacturer_data") or {}),
        **(item.get("manufacturer_data") or {}),
    }
    current["service_data"] = {
        **(current.get("service_data") or {}),
        **(item.get("service_data") or {}),
    }
    current["connectable"] = bool(current.get("connectable") or item.get("connectable"))
    current["last_seen"] = item.get("last_seen") or current.get("last_seen")
    if current.get("device_type") != "switchbot" and item.get("device_type") == "switchbot":
        current["device_type"] = "switchbot"
    if item.get("name") and (not current.get("name") or current.get("name") == "Unknown"):
        current["name"] = item.get("name")
    return current

async def _scan_once(timeout: int, interface: str | None) -> list[dict[str, Any]]:
    from bleak import BleakScanner
    kwargs: dict[str, Any] = {"timeout": timeout, "return_adv": True}
    if interface:
        kwargs["adapter"] = interface
    try:
        devices = await BleakScanner.discover(**kwargs)
    except TypeError:
        kwargs.pop("adapter", None)
        try:
            devices = await BleakScanner.discover(**kwargs)
        except TypeError:
            kwargs.pop("return_adv", None)
            devices = await BleakScanner.discover(**kwargs)
    result: list[dict[str, Any]] = []
    if isinstance(devices, dict):
        iterable = devices.values()
    else:
        iterable = ((device, None) for device in devices)
    for entry in iterable:
        if isinstance(entry, tuple) and len(entry) == 2:
            device, adv = entry
        else:
            device, adv = entry, None
        manufacturer_data = _normalize_manufacturer_data(
            getattr(adv, "manufacturer_data", None)
            or getattr(device, "metadata", {}).get("manufacturer_data", {})
            or {}
        )
        service_data = _normalize_service_data(
            getattr(adv, "service_data", None)
            or getattr(device, "metadata", {}).get("service_data", {})
            or {}
        )
        service_uuids = list(
            getattr(adv, "service_uuids", None)
            or getattr(device, "metadata", {}).get("uuids", [])
            or []
        )
        name = getattr(device, "name", None) or getattr(adv, "local_name", None) or "Unknown"
        result.append({
            "name": name,
            "address": getattr(device, "address", None),
            "rssi": getattr(adv, "rssi", None) if adv is not None else getattr(device, "rssi", None),
            "device_type": (
                "switchbot" if _looks_like_switchbot(name, manufacturer_data, service_data, service_uuids) else "ble"
            ),
            "service_uuids": service_uuids,
            "manufacturer_data": manufacturer_data,
            "service_data": service_data,
            "connectable": bool(getattr(adv, "connectable", None)) if adv is not None else None,
            "last_seen": _now_iso(),
        })
    return result

async def _discover_target(
    *,
    timeout: int,
    retry: int,
    interface: str | None,
    device_name: str | None,
    mac_address: str | None,
    service_uuid: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    merged: dict[str, dict[str, Any]] = {}
    interface_used: str | None = interface
    for _round in range(retry):
        devices = await _scan_once(timeout, interface)
        for item in devices:
            if not _matches_filters(
                address=str(item.get("address") or ""),
                name=item.get("name"),
                service_uuids=list(item.get("service_uuids") or []),
                device_name=device_name,
                mac_address=mac_address,
                service_uuid=service_uuid,
            ):
                continue
            key = str(item.get("address") or item.get("name") or "")
            if not key:
                continue
            current = merged.get(key)
            if current is None:
                merged[key] = item
            else:
                merged[key] = _merge_device(current, item)
    items = list(merged.values())
    items.sort(
        key=lambda x: (
            0 if x.get("device_type") == "switchbot" else 1,
            -(int(x["rssi"]) if isinstance(x.get("rssi"), int) else -9999),
            str(x.get("name") or ""),
            str(x.get("address") or ""),
        )
    )
    if mac_address:
        for item in items:
            if str(item.get("address") or "").casefold() == mac_address.casefold():
                return item, None, interface_used
        return (
            None,
            {
                "code": "not_found",
                "message": _(
                    "err.not_found",
                    default="No SwitchBot BLE device matched the provided mac_address.",
                    mac_address=mac_address,
                ),
            },
            interface_used,
        )
    if device_name:
        needle = device_name.casefold()
        matches = [item for item in items if needle in str(item.get("name") or "").casefold()]
        if not matches:
            return (
                None,
                {
                    "code": "not_found",
                    "message": _(
                        "err.not_found",
                        default="No SwitchBot BLE device matched the provided device_name.",
                        device_name=device_name,
                    ),
                },
                interface_used,
            )
        if len(matches) > 1:
            return (
                None,
                {
                    "code": "ambiguous_target",
                    "message": _(
                        "err.ambiguous_target",
                        default="Multiple SwitchBot BLE devices matched the provided device_name.",
                        device_name=device_name,
                    ),
                    "matches": [
                        {"name": item.get("name"), "address": item.get("address")}
                        for item in matches[:10]
                    ],
                },
                interface_used,
            )
        return matches[0], None, interface_used
    return (
        None,
        {
            "code": "invalid_argument",
            "message": _(
                "err.invalid_argument",
                default="Either mac_address or device_name is required.",
            ),
        },
        interface_used,
    )

async def _read_device_status(
    *,
    device: dict[str, Any],
    timeout: int,
    limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from bleak import BleakClient
    address = str(device.get("address") or "")
    discovered_services: list[dict[str, Any]] = []
    capabilities: list[dict[str, Any]] = []
    characteristics: list[dict[str, Any]] = []
    raw_values: dict[str, str] = {}
    battery: int | None = None
    async with BleakClient(address, timeout=timeout) as client:
        services = getattr(client, "services", None)
        if services is None:
            try:
                services = await client.get_services()  # type: ignore[attr-defined]
            except Exception:
                services = None
        if services is not None:
            for service in services:
                service_item: dict[str, Any] = {
                    "uuid": getattr(service, "uuid", None),
                    "description": getattr(service, "description", None),
                    "characteristics": [],
                }
                for char in getattr(service, "characteristics", []) or []:
                    properties = list(getattr(char, "properties", []) or [])
                    char_item: dict[str, Any] = {
                        "uuid": getattr(char, "uuid", None),
                        "description": getattr(char, "description", None),
                        "properties": properties,
                    }
                    if "read" in {p.lower() for p in properties}:
                        try:
                            data = await client.read_gatt_char(getattr(char, "uuid"))
                            hex_value = data.hex()
                            char_item["value_hex"] = hex_value
                            raw_values[str(getattr(char, "uuid", ""))] = hex_value
                            if str(getattr(char, "uuid", "")).casefold() == _BATTERY_UUID:
                                try:
                                    battery = int(data[0])
                                except Exception:
                                    battery = battery
                        except Exception as exc:
                            char_item["read_error"] = str(exc)
                    service_item["characteristics"].append(char_item)
                    characteristics.append(char_item)
                discovered_services.append(service_item)
                capabilities.append({
                    "uuid": getattr(service, "uuid", None),
                    "description": getattr(service, "description", None),
                    "characteristic_count": len(service_item["characteristics"]),
                })
    if limit > 0:
        characteristics = characteristics[:limit]
        discovered_services = discovered_services[:limit]
    status = {
        "connected": True,
        "battery": battery if battery is not None else device.get("battery"),
        "services": discovered_services,
        "characteristics": characteristics,
        "raw_values": raw_values,
        "source": "gatt",
    }
    return status, {"capabilities": capabilities}

def _status_from_advertisement(device: dict[str, Any]) -> dict[str, Any] | None:
    manufacturer_data = dict(device.get("manufacturer_data") or {})
    service_data = dict(device.get("service_data") or {})
    return _decode_switchbot_from_adv(
        manufacturer_data=manufacturer_data,
        service_data=service_data,
    )


def _format_text(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        error = result.get("error", {})
        return _("msg.error_fmt", default="Error: {msg}").format(
            msg=error.get("message", _("msg.unknown_error", default="unknown error"))
        )
    device = result.get("device", {}) or {}
    status = result.get("status", {}) or {}
    lines = [
        _(
            "msg.summary",
            default="SwitchBot BLE status fetched: {device_name} ({device_id}).",
            device_name=device.get("devname") or device.get("name") or "(unknown)",
            device_id=device.get("dev") or device.get("address") or "(unknown)",
        ),
        f"Address: {device.get('address') or '-'}",
        f"RSSI: {device.get('rssi')}",
        f"Model: {status.get('model') or device.get('device_type') or '-'}",
        f"Temperature: {status.get('temperature')}",
        f"Humidity: {status.get('humidity')}",
        f"Battery: {status.get('battery')}",
        f"Power: {status.get('power')}",
        f"Position: {status.get('position')}",
        f"Motion: {status.get('motion')}",
        f"Door: {status.get('door_state')}",
        f"Lock: {status.get('lock_state')}",
        f"Brightness: {status.get('brightness')}",
        f"PowerW: {status.get('power_w')}",
        f"Connected: {status.get('connected')}",
        f"Source: {status.get('source') or '-'}",
    ]
    services = status.get("services") or []
    characteristics = status.get("characteristics") or []
    if services or characteristics:
        lines.append(f"Services: {len(services)}")
        lines.append(f"Characteristics: {len(characteristics)}")
        for item in characteristics[:10]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- {uuid} props={props} value={value}".format(
                    uuid=item.get("uuid") or "(unknown)",
                    props=", ".join(item.get("properties") or []) or "-",
                    value=item.get("value_hex") or item.get("read_error") or "-",
                )
            )
    return chr(10).join(lines)

def run_tool(args: dict[str, Any]) -> str:
    output_format = str(args.get("fmt") or "json").lower()
    interface = args.get("interface")
    device_name = args.get("devname")
    mac_address = args.get("mac")
    service_uuid = args.get("service_uuid")
    try:
        timeout = int(args.get("timeout", 8))
        retry = int(args.get("retry", 2))
        limit = int(args.get("limit", 0))
    except Exception:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_numeric",
                    default="Timeout, retry, and limit must be integers.",
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
    if timeout <= 0 or retry <= 0 or limit < 0:
        payload = {
            "ok": False,
            "error": {
                "code": "invalid_argument",
                "message": _(
                    "err.invalid_range",
                    default="Timeout and retry must be greater than 0; limit must be 0 or greater.",
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
    try:
        import bleak  # noqa: F401
    except ImportError:
        payload = {
            "ok": False,
            "error": {
                "code": "bleak_missing",
                "message": _(
                    "err.bleak_missing",
                    default=(
                        "Error: 'bleak' library is not installed. Please install it using:" + chr(10) + "pip install bleak"
                    ),
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    started = time.perf_counter()
    try:
        device, err, interface_used = asyncio.run(
            _discover_target(
                timeout=timeout,
                retry=retry,
                interface=str(interface) if interface else None,
                device_name=str(device_name) if device_name else None,
                mac_address=str(mac_address) if mac_address else None,
                service_uuid=str(service_uuid) if service_uuid else None,
            )
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
        adv_status = _status_from_advertisement(device)
        status: dict[str, Any]
        extra: dict[str, Any]
        if adv_status is not None:
            status = adv_status
            caps = ["advertisement"]
            for key in (
                "temperature",
                "humidity",
                "battery",
                "power",
                "is_on",
                "position",
                "moving",
                "motion",
                "door_state",
                "lock_state",
                "brightness",
                "power_w",
            ):
                if status.get(key) is not None:
                    caps.append(key)
            extra = {"capabilities": caps}
        else:
            status, extra = asyncio.run(
                _read_device_status(device=device, timeout=timeout, limit=limit)
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "ok": True,
            "device": {
                "dev": device.get("address"),
                "devname": device.get("name"),
                "device_type": status.get("model") or device.get("device_type"),
                "hub_id": None,
                "online": True,
                "battery": status.get("battery"),
                "reachable": True,
                "address": device.get("address"),
                "rssi": device.get("rssi"),
                "service_uuids": device.get("service_uuids") or [],
                "manufacturer_data": device.get("manufacturer_data") or {},
                "service_data": device.get("service_data") or {},
                "connectable": device.get("connectable"),
                "last_seen": device.get("last_seen"),
            },
            "status": status,
            "capabilities": extra.get("capabilities", []),
            "interface_used": interface_used,
            "elapsed_ms": elapsed_ms,
            "last_updated": _now_iso(),
            "account": {
                "source": "local_ble",
                "authenticated": True,
            },
        }
        if output_format == "text":
            return _format_text(result)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        err_msg = str(exc)
        if sys.platform.startswith("linux"):
            if (
                "Permission" in err_msg
                or "AccessDenied" in err_msg
                or "dbus" in err_msg.lower()
                or "notready" in err_msg.lower()
            ):
                payload = {
                    "ok": False,
                    "error": {
                        "code": "network_error",
                        "message": _(
                            "err.linux_permission",
                            default=(
                                "Error during BLE operation: {err_msg}" + chr(10)*2 + "[Linux/Raspberry Pi Permission Guide]" + chr(10) + "You might lack permissions to access the Bluetooth socket. Try one of the following:" + chr(10) + "1. Add your user to the bluetooth group (recommended):" + chr(10) + "   sudo usermod -aG bluetooth $USER" + chr(10) + "   (Requires restart or re-login)" + chr(10) + "2. Grant permissions directly to the Python binary:" + chr(10) + "   sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python))"
                            ),
                            err_msg=err_msg,
                        ),
                    },
                }
                return (
                    json.dumps(payload, ensure_ascii=False, indent=2)
                    if output_format == "text"
                    else json.dumps(payload, ensure_ascii=False)
                )
        elif sys.platform == "darwin":
            if (
                "CoreBluetooth" in err_msg
                or "permission" in err_msg.lower()
                or "auth" in err_msg.lower()
            ):
                payload = {
                    "ok": False,
                    "error": {
                        "code": "network_error",
                        "message": _(
                            "err.macos_permission",
                            default=(
                                "Error during BLE operation: {err_msg}" + chr(10)*2 + "[macOS Permission Guide]" + chr(10) + "Bluetooth access might have been denied by macOS security restrictions." + chr(10) + "Please open 'System Settings > Privacy & Security > Bluetooth' and ensure your terminal, VS Code, or Python process is allowed to access Bluetooth."
                            ),
                            err_msg=err_msg,
                        ),
                    },
                }
                return (
                    json.dumps(payload, ensure_ascii=False, indent=2)
                    if output_format == "text"
                    else json.dumps(payload, ensure_ascii=False)
                )
        payload = {
            "ok": False,
            "error": {
                "code": "request_failed",
                "message": _(
                    "err.operation_failed",
                    default="Error during BLE operation: {err_msg}",
                    err_msg=err_msg,
                ),
            },
        }
        return (
            _format_text(payload)
            if output_format == "text"
            else json.dumps(payload, ensure_ascii=False)
        )

