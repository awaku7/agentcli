"""Tests for Matter tools (Phase 1-3).

Requires: pytest
Usage: pytest tests/test_matter_tools.py -v
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from tests.matter_fixtures import (
    BRIDGES_DICT,
    BRIDGES_JSON,
    CONTROLLERS_DICT,
    CONTROLLERS_JSON,
    DEVICES_DICT,
    DEVICES_JSON,
    EMPTY_DICT_DATA,
    EMPTY_LIST,
    FIELD_MISSING,
    MALFORMED_JSON,
)

# ---------------------------------------------------------------------------
# Monkeys / helpers
# ---------------------------------------------------------------------------


def _set_env(monkeypatch: pytest.MonkeyPatch, key: str, value: str) -> None:
    """Set env var and register cleanup."""
    monkeypatch.setenv(key, value)


def _unset_env(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    """Unset env var."""
    monkeypatch.delenv(key, raising=False)


def _import_and_run(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Import a matter tool module and run it, returning parsed JSON."""
    import importlib

    mod = importlib.import_module(f"uagent.tools.{tool_name}_tool")
    raw = mod.run_tool(args)
    return json.loads(raw)


def _assert_ok(result: dict[str, Any]) -> None:
    assert result.get("ok") is True, f"Expected ok=True, got: {result}"


def _assert_error(
    result: dict[str, Any], expected_code: str
) -> None:
    assert result.get("ok") is False, f"Expected ok=False, got: {result}"
    error = result.get("error", {})
    assert error.get("code") == expected_code, (
        f"Expected error code '{expected_code}', got '{error.get('code')}': {result}"
    )


# ===================================================================
# matter_controller_list
# ===================================================================


class TestMatterControllerList:
    TOOL = "matter_controller_list"

    def test_all_controllers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", CONTROLLERS_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_ok(result)
        assert result["count"] == 3
        assert len(result["items"]) == 3
        assert result["controller"]["scope"] == "all"

    def test_filter_by_ctrl_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", CONTROLLERS_JSON)
        result = _import_and_run(self.TOOL, {"ctrl": "ctrl-001"})
        _assert_ok(result)
        assert result["count"] == 1
        assert result["items"][0]["ctrl"] == "ctrl-001"

    def test_filter_no_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", CONTROLLERS_JSON)
        result = _import_and_run(self.TOOL, {"ctrl": "nonexistent"})
        _assert_error(result, "not_found")

    def test_config_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _unset_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_FILE")
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "config_missing")

    def test_malformed_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", MALFORMED_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "invalid_config")

    def test_empty_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", EMPTY_LIST)
        result = _import_and_run(self.TOOL, {})
        _assert_ok(result)
        assert result["count"] == 0

    def test_dict_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(
            monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", json.dumps(CONTROLLERS_DICT)
        )
        result = _import_and_run(self.TOOL, {})
        _assert_ok(result)
        assert result["count"] == 3

    def test_text_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", CONTROLLERS_JSON)
        import importlib

        mod = importlib.import_module(f"uagent.tools.{self.TOOL}_tool")
        raw = mod.run_tool({"fmt": "text"})
        assert isinstance(raw, str)
        assert "Matter controllers:" in raw
        assert "Living Room Controller" in raw

    def test_field_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Items with missing fields should not crash."""
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", FIELD_MISSING)
        result = _import_and_run(self.TOOL, {})
        _assert_ok(result)
        assert result["count"] == 1
        item = result["items"][0]
        assert item["ctrl"] == "orphan-device"
        assert item["controller_name"] is None


# ===================================================================
# matter_bridge_list
# ===================================================================


class TestMatterBridgeList:
    TOOL = "matter_bridge_list"

    def test_all_bridges(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON", BRIDGES_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_ok(result)
        assert result["count"] == 2

    def test_filter_by_bridge_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON", BRIDGES_JSON)
        result = _import_and_run(self.TOOL, {"bridge": "bridge-001"})
        _assert_ok(result)
        assert result["count"] == 1
        assert result["items"][0]["bridge"] == "bridge-001"
        assert result["items"][0]["bridge_name"] == "Kitchen Bridge"

    def test_filter_no_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON", BRIDGES_JSON)
        result = _import_and_run(self.TOOL, {"bridge": "nonexistent"})
        _assert_error(result, "not_found")

    def test_config_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _unset_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_BRIDGES_FILE")
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "config_missing")

    def test_dict_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(
            monkeypatch, "UAGENT_MATTER_BRIDGES_JSON", json.dumps(BRIDGES_DICT)
        )
        result = _import_and_run(self.TOOL, {})
        _assert_ok(result)
        assert result["count"] == 2

    def test_device_ids_from_devices_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """bridge-002 has device list with dict items."""
        _set_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON", BRIDGES_JSON)
        result = _import_and_run(self.TOOL, {"bridge": "bridge-002"})
        _assert_ok(result)
        item = result["items"][0]
        assert "sensor-garage-01" in item["device_ids"]
        assert "lock-garage-01" in item["device_ids"]

    def test_text_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON", BRIDGES_JSON)
        import importlib

        mod = importlib.import_module(f"uagent.tools.{self.TOOL}_tool")
        raw = mod.run_tool({"fmt": "text"})
        assert isinstance(raw, str)
        assert "Matter bridges:" in raw


# ===================================================================
# matter_device_status
# ===================================================================


class TestMatterDeviceStatus:
    TOOL = "matter_device_status"

    def test_device_by_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "light-kitchen-01"})
        _assert_ok(result)
        assert result["device"]["dev"] == "light-kitchen-01"
        assert result["device"]["devname"] == "Kitchen Ceiling Light"
        assert result["device"]["device_type"] == "light"
        assert result["device"]["vendor"] == "Philips"

    def test_device_with_ctrl_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "ctrl": "ctrl-001"}
        )
        _assert_ok(result)

    def test_device_with_bridge_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "bridge": "bridge-001"}
        )
        _assert_ok(result)

    def test_device_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "nonexistent"})
        _assert_error(result, "not_found")

    def test_device_id_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "invalid_argument")

    def test_config_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _unset_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_DEVICES_FILE")
        _unset_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_FILE")
        _unset_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_BRIDGES_FILE")
        result = _import_and_run(self.TOOL, {"dev": "light-kitchen-01"})
        _assert_error(result, "config_missing")

    def test_device_attributes_light(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "light-kitchen-01"})
        _assert_ok(result)
        attrs = result["device"].get("device_attributes") or {}
        assert attrs.get("onOff") is True
        assert attrs.get("brightness") == 80

    def test_device_attributes_sensor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "sensor-garage-01"})
        _assert_ok(result)
        attrs = result["device"].get("device_attributes") or {}
        assert attrs.get("temperature") == 22.5
        assert attrs.get("humidity") == 55

    def test_endpoint_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "endpoint": "ep1"}
        )
        _assert_ok(result)
        assert len(result["endpoints"]) == 1
        assert result["endpoints"][0]["endpoint_id"] == "ep1"

    def test_controller_data_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Device found via controllers JSON."""
        _set_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON", CONTROLLERS_JSON)
        _unset_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON")
        result = _import_and_run(self.TOOL, {"dev": "light-kitchen-01"})
        # controllers JSON doesn't have device detail, so not found is OK
        assert result.get("ok") is False

    def test_text_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        import importlib

        mod = importlib.import_module(f"uagent.tools.{self.TOOL}_tool")
        raw = mod.run_tool({"dev": "light-kitchen-01", "fmt": "text"})
        assert isinstance(raw, str)
        assert "Kitchen Ceiling Light" in raw


# ===================================================================
# matter_endpoint_list
# ===================================================================


class TestMatterEndpointList:
    TOOL = "matter_endpoint_list"

    def test_list_endpoints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "light-kitchen-01"})
        _assert_ok(result)
        assert result["count"] == 1
        assert result["endpoints"][0]["endpoint_id"] == "ep1"
        assert len(result["endpoints"][0]["clusters"]) == 2

    def test_device_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "invalid_argument")

    def test_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "nonexistent"})
        _assert_error(result, "not_found")

    def test_text_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        import importlib

        mod = importlib.import_module(f"uagent.tools.{self.TOOL}_tool")
        raw = mod.run_tool({"dev": "light-kitchen-01", "fmt": "text"})
        assert isinstance(raw, str)
        assert "Matter device endpoints:" in raw


# ===================================================================
# matter_cluster_list
# ===================================================================


class TestMatterClusterList:
    TOOL = "matter_cluster_list"

    def test_list_clusters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {"dev": "light-kitchen-01"})
        _assert_ok(result)
        assert result["count"] >= 2  # device-level + endpoint-level clusters
        cluster_names = {c.get("cluster_name") for c in result["clusters"]}
        assert "On/Off" in cluster_names
        assert "Level Control" in cluster_names

    def test_endpoint_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "endpoint": "ep1"}
        )
        _assert_ok(result)
        assert result["count"] >= 2

    def test_device_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "invalid_argument")

    def test_text_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        import importlib

        mod = importlib.import_module(f"uagent.tools.{self.TOOL}_tool")
        raw = mod.run_tool({"dev": "light-kitchen-01", "fmt": "text"})
        assert isinstance(raw, str)
        assert "Matter clusters:" in raw


# ===================================================================
# matter_control
# ===================================================================


class TestMatterControl:
    TOOL = "matter_control"

    def test_on_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "action": "on"}
        )
        _assert_ok(result)
        assert result["command"]["action"] == "on"
        assert result["command"]["queued_to"] is not None

    def test_off_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "switch-kitchen-01", "action": "off"}
        )
        _assert_ok(result)

    def test_lock_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "lock-garage-01", "action": "lock"}
        )
        _assert_ok(result)
        assert result["command"]["action"] == "lock"

    def test_set_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "action": "set_value", "value": 50}
        )
        _assert_ok(result)
        assert result["command"]["value"] == 50

    def test_set_value_without_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "action": "set_value"}
        )
        _assert_error(result, "invalid_argument")

    def test_value_out_of_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL,
            {"dev": "light-kitchen-01", "action": "set_value", "value": 999},
        )
        _assert_error(result, "invalid_argument")

    def test_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "action": "on", "dry_run": True}
        )
        _assert_ok(result)
        assert result.get("command", {}).get("dry_run") is True

    def test_unsupported_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sensor doesn't support on/off."""
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "sensor-garage-01", "action": "on"}
        )
        _assert_error(result, "unsupported_action")

    def test_invalid_action(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "action": "fly"}
        )
        _assert_error(result, "invalid_argument")

    def test_device_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(
            self.TOOL, {"dev": "nonexistent", "action": "on"}
        )
        _assert_error(result, "not_found")

    def test_device_id_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        result = _import_and_run(self.TOOL, {})
        _assert_error(result, "invalid_argument")

    def test_config_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _unset_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_DEVICES_FILE")
        _unset_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_CONTROLLERS_FILE")
        _unset_env(monkeypatch, "UAGENT_MATTER_BRIDGES_JSON")
        _unset_env(monkeypatch, "UAGENT_MATTER_BRIDGES_FILE")
        result = _import_and_run(
            self.TOOL, {"dev": "light-kitchen-01", "action": "on"}
        )
        _assert_error(result, "config_missing")

    def test_text_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_env(monkeypatch, "UAGENT_MATTER_DEVICES_JSON", DEVICES_JSON)
        import importlib

        mod = importlib.import_module(f"uagent.tools.{self.TOOL}_tool")
        raw = mod.run_tool(
            {"dev": "light-kitchen-01", "action": "on", "fmt": "text"}
        )
        assert isinstance(raw, str)
        assert "queued" in raw or "Error" in raw
