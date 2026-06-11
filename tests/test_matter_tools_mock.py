from __future__ import annotations

import json

import pytest


def _loads(s: str) -> dict:
    obj = json.loads(s)
    assert isinstance(obj, dict)
    return obj


def _set_matter_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    controllers: object | None = None,
    bridges: object | None = None,
    devices: object | None = None,
) -> None:
    for name in (
        "UAGENT_MATTER_CONTROLLERS_JSON",
        "UAGENT_MATTER_CONTROLLERS_FILE",
        "UAGENT_MATTER_BRIDGES_JSON",
        "UAGENT_MATTER_BRIDGES_FILE",
        "UAGENT_MATTER_DEVICES_JSON",
        "UAGENT_MATTER_DEVICES_FILE",
    ):
        monkeypatch.delenv(name, raising=False)

    if controllers is not None:
        monkeypatch.setenv("UAGENT_MATTER_CONTROLLERS_JSON", json.dumps(controllers))
    if bridges is not None:
        monkeypatch.setenv("UAGENT_MATTER_BRIDGES_JSON", json.dumps(bridges))
    if devices is not None:
        monkeypatch.setenv("UAGENT_MATTER_DEVICES_JSON", json.dumps(devices))


def test_matter_controller_list_returns_normalized_items(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools.matter_controller_list_tool import run_tool

    _set_matter_env(
        monkeypatch,
        controllers=[
            {
                "controllerId": "ctrl-1",
                "controllerName": "Main Controller",
                "deviceCount": 2,
                "bridgeIds": ["bridge-1"],
                "reachable": True,
                "updatedAt": "2026-01-01T00:00:00Z",
                "transport": "thread",
            }
        ],
    )

    obj = _loads(run_tool({"output_format": "json"}))
    assert obj["ok"] is True
    assert obj["count"] == 1
    assert obj["controller"]["scope"] == "all"
    assert obj["items"][0]["controller_id"] == "ctrl-1"
    assert obj["items"][0]["controller_name"] == "Main Controller"
    assert obj["items"][0]["bridge_ids"] == ["bridge-1"]


def test_matter_controller_list_filters_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools.matter_controller_list_tool import run_tool

    _set_matter_env(
        monkeypatch,
        controllers=[
            {"controllerId": "ctrl-1", "controllerName": "Main"},
            {"controllerId": "ctrl-2", "controllerName": "Backup"},
        ],
    )

    obj = _loads(run_tool({"controller_id": "ctrl-2"}))
    assert obj["ok"] is True
    assert obj["count"] == 1
    assert obj["controller"]["scope"] == "filtered"
    assert obj["items"][0]["controller_id"] == "ctrl-2"


def test_matter_bridge_list_returns_normalized_items(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools.matter_bridge_list_tool import run_tool

    _set_matter_env(
        monkeypatch,
        bridges=[
            {
                "bridgeId": "bridge-1",
                "bridgeName": "Hall Bridge",
                "controllerId": "ctrl-1",
                "deviceIds": ["dev-1", "dev-2"],
                "deviceCount": 2,
                "reachable": True,
                "updatedAt": "2026-01-01T00:00:00Z",
            }
        ],
    )

    obj = _loads(run_tool({}))
    assert obj["ok"] is True
    assert obj["count"] == 1
    assert obj["bridge"]["scope"] == "all"
    assert obj["items"][0]["bridge_id"] == "bridge-1"
    assert obj["items"][0]["device_ids"] == ["dev-1", "dev-2"]


def test_matter_device_status_returns_status_endpoints_and_clusters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools.matter_device_status_tool import run_tool

    _set_matter_env(
        monkeypatch,
        devices=[
            {
                "deviceId": "dev-1",
                "deviceName": "Lamp",
                "deviceType": "light",
                "vendor": "Acme",
                "bridgeId": "bridge-1",
                "controllerId": "ctrl-1",
                "reachable": True,
                "updatedAt": "2026-01-01T00:00:00Z",
                "status": {"power": "on", "brightness": 80},
                "endpoints": [
                    {
                        "endpointId": "1",
                        "deviceType": "light",
                        "clusters": [
                            {"clusterId": "0006", "clusterName": "OnOff"},
                        ],
                    },
                    {
                        "endpointId": "2",
                        "deviceType": "light",
                        "clusters": [
                            {"clusterId": "0008", "clusterName": "LevelControl"},
                        ],
                    },
                ],
                "clusters": [
                    {"clusterId": "0000", "clusterName": "Basic"},
                ],
            }
        ],
    )

    obj = _loads(run_tool({"device_id": "dev-1"}))
    assert obj["ok"] is True
    assert obj["device"]["device_name"] == "Lamp"
    assert obj["status"]["power"] == "on"
    assert len(obj["endpoints" ]) == 2
    assert {c["cluster_id"] for c in obj["clusters"]} == {"0000", "0006", "0008"}


def test_matter_device_status_endpoint_filter_limits_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools.matter_device_status_tool import run_tool

    _set_matter_env(
        monkeypatch,
        devices=[
            {
                "deviceId": "dev-1",
                "endpoints": [
                    {"endpointId": "1", "clusters": [{"clusterId": "0006"}]},
                    {"endpointId": "2", "clusters": [{"clusterId": "0008"}]},
                ],
            }
        ],
    )

    obj = _loads(run_tool({"device_id": "dev-1", "endpoint": "2"}))
    assert obj["ok"] is True
    assert [ep["endpoint_id"] for ep in obj["endpoints"]] == ["2"]
    assert [c["cluster_id"] for c in obj["clusters"]] == ["0008"]


def test_matter_device_status_ambiguous_target_when_multiple_sources_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uagent.tools.matter_device_status_tool import run_tool

    _set_matter_env(
        monkeypatch,
        devices=[
            {"deviceId": "dev-1", "controllerId": "ctrl-1"},
            {"deviceId": "dev-1", "controllerId": "ctrl-2"},
        ],
    )

    obj = _loads(run_tool({"device_id": "dev-1"}))
    assert obj["ok"] is False
    assert obj["error"]["code"] == "ambiguous_target"


def test_matter_endpoint_list_returns_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools.matter_endpoint_list_tool import run_tool

    _set_matter_env(
        monkeypatch,
        devices=[
            {
                "deviceId": "dev-1",
                "deviceName": "Lamp",
                "deviceType": "light",
                "vendor": "Acme",
                "bridgeId": "bridge-1",
                "controllerId": "ctrl-1",
                "reachable": True,
                "updatedAt": "2026-01-01T00:00:00Z",
                "endpoints": [
                    {"endpointId": "1", "deviceType": "light", "clusters": [{"clusterId": "0006"}]},
                    {"endpointId": "2", "deviceType": "light", "clusters": [{"clusterId": "0008"}]},
                ],
            }
        ],
    )

    obj = _loads(run_tool({"device_id": "dev-1"}))
    assert obj["ok"] is True
    assert obj["count"] == 2
    assert [ep["endpoint_id"] for ep in obj["endpoints"]] == ["1", "2"]
    assert obj["device"]["device_name"] == "Lamp"


def test_matter_cluster_list_returns_clusters(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools.matter_cluster_list_tool import run_tool

    _set_matter_env(
        monkeypatch,
        devices=[
            {
                "deviceId": "dev-1",
                "deviceName": "Lamp",
                "deviceType": "light",
                "vendor": "Acme",
                "bridgeId": "bridge-1",
                "controllerId": "ctrl-1",
                "reachable": True,
                "updatedAt": "2026-01-01T00:00:00Z",
                "clusters": [{"clusterId": "0000", "clusterName": "Basic"}],
                "endpoints": [
                    {"endpointId": "1", "deviceType": "light", "clusters": [{"clusterId": "0006", "clusterName": "OnOff"}]},
                    {"endpointId": "2", "deviceType": "light", "clusters": [{"clusterId": "0008", "clusterName": "LevelControl"}]},
                ],
            }
        ],
    )

    obj = _loads(run_tool({"device_id": "dev-1"}))
    assert obj["ok"] is True
    assert obj["count"] == 3
    assert {c["cluster_id"] for c in obj["clusters"]} == {"0000", "0006", "0008"}
    assert obj["device"]["device_name"] == "Lamp"


def test_matter_config_missing_when_no_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from uagent.tools.matter_controller_list_tool import run_tool

    _set_matter_env(monkeypatch)
    obj = _loads(run_tool({}))
    assert obj["ok"] is False
    assert obj["error"]["code"] == "config_missing"
