"""Test fixtures for Matter tools.

Shared JSON payloads that simulate Matter controller/bridge/device configurations.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Controller fixture
# ---------------------------------------------------------------------------
CONTROLLERS_RAW: list[dict[str, Any]] = [
    {
        "id": "ctrl-001",
        "name": "Living Room Controller",
        "deviceCount": 3,
        "bridgeIds": ["bridge-001"],
        "room": "Living Room",
        "floor": 1,
        "transport": "ethernet",
        "reachable": True,
        "lastUpdated": "2026-06-22T10:00:00+09:00",
    },
    {
        "id": "ctrl-002",
        "name": "Office Controller",
        "deviceCount": 2,
        "bridgeIds": [],
        "room": "Office",
        "floor": 2,
        "transport": "wifi",
        "online": True,
        "last_updated": "2026-06-22T10:05:00+09:00",
    },
    {
        "id": "ctrl-003",
        "name": "Offline Controller",
        "deviceCount": 0,
        "bridgeIds": [],
        "room": "Basement",
        "floor": -1,
        "transport": "wifi",
        "reachable": False,
        "last_updated": "2026-06-20T00:00:00+09:00",
    },
]

CONTROLLERS_JSON: str = json.dumps(CONTROLLERS_RAW, ensure_ascii=False)
CONTROLLERS_DICT: dict[str, Any] = {"controllers": CONTROLLERS_RAW}

# ---------------------------------------------------------------------------
# Bridge fixture
# ---------------------------------------------------------------------------
BRIDGES_RAW: list[dict[str, Any]] = [
    {
        "id": "bridge-001",
        "name": "Kitchen Bridge",
        "controllerId": "ctrl-001",
        "deviceCount": 2,
        "deviceIds": ["light-kitchen-01", "switch-kitchen-01"],
        "transport": "thread",
        "reachable": True,
        "room": "Kitchen",
        "floor": 1,
        "lastUpdated": "2026-06-22T10:00:00+09:00",
    },
    {
        "id": "bridge-002",
        "name": "Garage Bridge",
        "controllerId": "ctrl-001",
        "devices": [
            {"deviceId": "sensor-garage-01"},
            {"deviceId": "lock-garage-01"},
        ],
        "transport": "wifi",
        "online": True,
        "room": "Garage",
        "floor": 1,
        "last_updated": "2026-06-22T09:00:00+09:00",
    },
]

BRIDGES_JSON: str = json.dumps(BRIDGES_RAW, ensure_ascii=False)
BRIDGES_DICT: dict[str, Any] = {"bridges": BRIDGES_RAW}

# ---------------------------------------------------------------------------
# Device fixture
# ---------------------------------------------------------------------------
DEVICES_RAW: list[dict[str, Any]] = [
    {
        "id": "light-kitchen-01",
        "name": "Kitchen Ceiling Light",
        "deviceType": "light",
        "vendor": "Philips",
        "controllerId": "ctrl-001",
        "bridgeId": "bridge-001",
        "room": "Kitchen",
        "floor": 1,
        "reachable": True,
        "onOff": True,
        "brightness": 80,
        "colorTemperature": 4000,
        "lastUpdated": "2026-06-22T10:30:00+09:00",
        "endpoints": [
            {
                "endpointId": "ep1",
                "deviceType": "light",
                "label": "Main Light",
                "clusters": [
                    {
                        "clusterId": "on_off",
                        "clusterName": "On/Off",
                        "attributes": [{"name": "onOff", "value": True}],
                        "commands": ["on", "off", "toggle"],
                    },
                    {
                        "clusterId": "level_control",
                        "clusterName": "Level Control",
                        "attributes": [{"name": "currentLevel", "value": 80}],
                        "commands": ["move_to_level"],
                    },
                ],
            },
        ],
        "clusters": [
            {
                "clusterId": "on_off",
                "clusterName": "On/Off",
                "attributes": [{"name": "onOff", "value": True}],
                "commands": ["on", "off", "toggle"],
            },
        ],
    },
    {
        "id": "switch-kitchen-01",
        "name": "Kitchen Switch",
        "deviceType": "switch",
        "vendor": "Legrand",
        "controllerId": "ctrl-001",
        "bridgeId": "bridge-001",
        "room": "Kitchen",
        "floor": 1,
        "reachable": True,
        "onOff": False,
        "lastUpdated": "2026-06-22T08:00:00+09:00",
        "endpoints": [
            {
                "endpointId": "ep1",
                "deviceType": "switch",
                "label": "Main Switch",
                "clusters": [
                    {
                        "clusterId": "on_off",
                        "clusterName": "On/Off",
                        "attributes": [{"name": "onOff", "value": False}],
                        "commands": ["on", "off"],
                    },
                ],
            },
        ],
        "clusters": [
            {
                "clusterId": "on_off",
                "clusterName": "On/Off",
                "attributes": [{"name": "onOff", "value": False}],
                "commands": ["on", "off"],
            },
        ],
    },
    {
        "id": "sensor-garage-01",
        "name": "Garage Temp Sensor",
        "deviceType": "temperature_sensor",
        "vendor": "Aqara",
        "controllerId": "ctrl-001",
        "bridgeId": "bridge-002",
        "room": "Garage",
        "floor": 1,
        "reachable": True,
        "temperature": 22.5,
        "humidity": 55,
        "battery": 80,
        "lastUpdated": "2026-06-22T10:15:00+09:00",
        "endpoints": [
            {
                "endpointId": "ep1",
                "deviceType": "temperature_sensor",
                "label": "Temperature",
                "clusters": [
                    {
                        "clusterId": "temperature",
                        "clusterName": "Temperature Measurement",
                        "attributes": [{"name": "measuredValue", "value": 2250}],
                        "commands": [],
                    },
                    {
                        "clusterId": "relative_humidity",
                        "clusterName": "Relative Humidity",
                        "attributes": [{"name": "measuredValue", "value": 5500}],
                        "commands": [],
                    },
                ],
            },
        ],
        "clusters": [],
    },
    {
        "id": "lock-garage-01",
        "name": "Garage Door Lock",
        "deviceType": "lock",
        "vendor": "Yale",
        "controllerId": "ctrl-001",
        "bridgeId": "bridge-002",
        "room": "Garage",
        "floor": 1,
        "reachable": True,
        "lockState": "locked",
        "battery": 65,
        "lastUpdated": "2026-06-22T09:00:00+09:00",
        "endpoints": [
            {
                "endpointId": "ep1",
                "deviceType": "lock",
                "label": "Main Lock",
                "clusters": [
                    {
                        "clusterId": "door_lock",
                        "clusterName": "Door Lock",
                        "attributes": [{"name": "lockState", "value": "locked"}],
                        "commands": ["lock", "unlock"],
                    },
                ],
            },
        ],
        "clusters": [],
    },
]

DEVICES_JSON: str = json.dumps(DEVICES_RAW, ensure_ascii=False)
DEVICES_DICT: dict[str, Any] = {"devices": DEVICES_RAW}

# ---------------------------------------------------------------------------
# Edge case / invalid fixtures
# ---------------------------------------------------------------------------
EMPTY_LIST: str = "[]"
EMPTY_DICT_DATA: str = json.dumps({"devices": []})
MALFORMED_JSON: str = "{invalid json here}"
FIELD_MISSING: str = json.dumps([{"id": "orphan-device"}])  # no name, type etc.
