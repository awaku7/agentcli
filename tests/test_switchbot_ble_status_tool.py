from __future__ import annotations

import json

from uagent.tools.switchbot_ble_status_tool import (
    _decode_meter_from_adv,
    _decode_switchbot_from_adv,
    _decode_temp_humidity_bytes,
    _format_text,
    run_tool,
)


def test_decode_temp_humidity_from_manufacturer_payload() -> None:
    # Sample from live Meter advertisement manufacturer_data[2409]
    mfr = "eb6b04860c2ee003099c39"
    decoded = _decode_meter_from_adv(
        manufacturer_data={"2409": mfr},
        service_data={},
    )
    assert decoded is not None
    assert decoded["temperature"] == 28.9
    assert decoded["humidity"] == 57
    assert decoded["connected"] is False
    assert decoded["source"] == "manufacturer_data"


def test_decode_temp_humidity_from_service_data() -> None:
    # Official service data layout: type, status, battery, temp_frac, temp_int, humidity
    # type=0x54 (Meter), battery=100, temp=29.1C, humidity=58
    svc = bytes([0x54, 0x00, 100, 0x01, 0x80 | 29, 58]).hex()
    decoded = _decode_meter_from_adv(
        manufacturer_data={},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["temperature"] == 29.1
    assert decoded["humidity"] == 58
    assert decoded["battery"] == 100
    assert decoded["model"] == "Meter"
    assert decoded["source"] == "service_data"


def test_decode_rejects_invalid_humidity() -> None:
    assert _decode_temp_humidity_bytes(bytes([0, 0x80, 127]), 50) is None


def test_decode_bot_from_service_data() -> None:
    # Bot: type=0x48, mode=on/off + state=off, battery=87
    svc = bytes([0x48, 0b11000000, 87]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Bot"
    assert decoded["mode"] == "on_off"
    assert decoded["power"] == "off"
    assert decoded["is_on"] is False
    assert decoded["battery"] == 87


def test_decode_curtain_from_service_data() -> None:
    # Curtain: type=0x63, calibrated+connectable, battery=66, moving + position 42
    svc = bytes([0x63, 0b11000000, 66, 0b10000000 | 42, (5 << 4) | 2]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Curtain"
    assert decoded["battery"] == 66
    assert decoded["moving"] is True
    assert decoded["position"] == 42
    assert decoded["light_level"] == 5
    assert decoded["device_chain"] == 2


def test_decode_motion_from_service_data() -> None:
    # Motion: type=0x73, motion=1, battery=55, last motion 10s, bright/middle
    # sensor bits: led=1,iot=1,distance=01(middle),light=10(bright) => 0b00110110
    svc = bytes([0x73, 0b01000000, 55, 0x00, 0x0A, 0b00110110]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Motion Sensor"
    assert decoded["motion"] is True
    assert decoded["battery"] == 55
    assert decoded["last_motion_seconds"] == 10
    assert decoded["sensing_distance"] == "middle"
    assert decoded["light_level"] == "bright"


def test_decode_contact_from_service_data() -> None:
    # Contact: type=0x64, motion=0, battery=90, door open + light
    svc = bytes([0x64, 0x00, 90, 0b00000010 | 0b00000001, 0x00, 0x05, 0x00, 0x08, 0b01010011]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Contact Sensor"
    assert decoded["door_state"] == "open"
    assert decoded["open"] is True
    assert decoded["light_level"] == "light"
    assert decoded["battery"] == 90
    assert decoded["last_motion_seconds"] == 5
    assert decoded["last_contact_seconds"] == 8


def test_decode_plug_from_manufacturer_data() -> None:
    # Plug Mini manufacturer payload (company id already stripped)
    # mac(6) + seq + state(on) + flags + wifi_rssi + power bytes
    mfr = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x01, 0x80, 0x00, 0xC8, 0x00, 123]).hex()
    svc = bytes([0x67, 0x00, 100]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={"2409": mfr},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Plug Mini"
    assert decoded["is_on"] is True
    assert decoded["power"] == "on"
    assert decoded["power_w"] == 12.3
    assert decoded["wifi_rssi"] == -56


def test_decode_lock_from_manufacturer_data() -> None:
    # Lock manufacturer payload: mac(6)+seq+lock_info(locked+closed)+extra
    mfr = bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x01, 0b10000000, 0x00, 0x00]).hex()
    svc = bytes([0x6F, 0x00, 77]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={"2409": mfr},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Smart Lock"
    assert decoded["lock_state"] == "locked"
    assert decoded["is_locked"] is True
    assert decoded["door_open"] is False
    assert decoded["battery"] == 77


def test_decode_hub_mini_from_service_data() -> None:
    svc = bytes([0x6D, 0x00]).hex()
    decoded = _decode_switchbot_from_adv(
        manufacturer_data={},
        service_data={"0000fd3d-0000-1000-8000-00805f9b34fb": svc},
    )
    assert decoded is not None
    assert decoded["model"] == "Hub Mini"
    assert decoded["online"] is True


def test_not_found_message_does_not_crash_i18n() -> None:
    out = run_tool({"mac": "AA:BB:CC:DD:EE:FF", "timeout": 1, "retry": 1, "fmt": "json"})
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["error"]["code"] in {"not_found", "request_failed", "bleak_missing"}
    assert "int" not in str(payload["error"].get("message", "")).lower() or "not callable" not in str(
        payload["error"].get("message", "")
    ).lower()


def test_format_text_includes_multi_device_fields() -> None:
    text = _format_text(
        {
            "ok": True,
            "device": {"devname": "Bot", "dev": "AA:BB", "address": "AA:BB", "rssi": -50},
            "status": {
                "model": "Bot",
                "power": "on",
                "battery": 80,
                "connected": False,
                "source": "service_data",
            },
        }
    )
    assert "Model: Bot" in text
    assert "Power: on" in text
    assert "Battery: 80" in text
