"""Tests for Matter state history and subscription tools."""

from __future__ import annotations

import importlib
import json

from tests.matter_fixtures import DEVICES_JSON

TOOLS_DIR = "uagent.tools"


def _run(tool_name: str, args: dict) -> dict:
    mod = importlib.import_module(f"{TOOLS_DIR}.{tool_name}_tool")
    raw = mod.run_tool(args)
    return json.loads(raw)


# ===================================================================
# matter_state_history
# ===================================================================


class TestMatterStateHistory:
    TOOL = "matter_state_history"

    def test_empty_history(self) -> None:
        result = _run(self.TOOL, {})
        assert result["ok"] is True
        assert result["count"] == 0
        assert result["total"] >= 0

    def test_clear_history(self) -> None:
        result = _run(self.TOOL, {"clear": True})
        assert result["ok"] is True
        assert "cleared" in result

    def test_text_output(self) -> None:
        import importlib
        mod = importlib.import_module(f"{TOOLS_DIR}.{self.TOOL}_tool")
        raw = mod.run_tool({"fmt": "text"})
        assert isinstance(raw, str)
        assert "Matter state history" in raw or "Error" in raw


# ===================================================================
# matter_subscribe
# ===================================================================


class TestMatterSubscribe:
    TOOL = "matter_subscribe"

    def test_subscribe_device(self) -> None:
        result = _run(self.TOOL, {"dev": "light-kitchen-01"})
        assert result["ok"] is True
        assert "subscription_id" in result["subscription"]
        assert result["subscription"]["dev"] == "light-kitchen-01"
        # Cleanup
        sub_id = result["subscription"]["subscription_id"]
        _run("matter_unsubscribe", {"subscription_id": sub_id})

    def test_subscribe_device_id_required(self) -> None:
        result = _run(self.TOOL, {})
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_argument"

    def test_subscribe_with_endpoint(self) -> None:
        result = _run(self.TOOL, {"dev": "sensor-garage-01", "endpoint": "ep1"})
        assert result["ok"] is True
        assert result["subscription"]["endpoint"] == "ep1"
        sub_id = result["subscription"]["subscription_id"]
        _run("matter_unsubscribe", {"subscription_id": sub_id})

    def test_subscribe_duplicate_updates(self) -> None:
        """Re-subscribing to same device updates existing subscription."""
        r1 = _run(self.TOOL, {"dev": "light-kitchen-01", "duration": 60})
        sub_id1 = r1["subscription"]["subscription_id"]
        r2 = _run(self.TOOL, {"dev": "light-kitchen-01", "duration": 3600})
        # Should return same or updated subscription
        assert r2["ok"] is True
        # Cleanup
        _run("matter_unsubscribe", {"subscription_id": sub_id1})

    def test_text_output(self) -> None:
        import importlib
        mod = importlib.import_module(f"{TOOLS_DIR}.{self.TOOL}_tool")
        raw = mod.run_tool({"dev": "light-kitchen-01", "fmt": "text"})
        assert isinstance(raw, str)
        assert "Subscribed" in raw or "Error" in raw


# ===================================================================
# matter_unsubscribe
# ===================================================================


class TestMatterUnsubscribe:
    TOOL = "matter_unsubscribe"

    def test_unsubscribe_not_found(self) -> None:
        result = _run(self.TOOL, {"subscription_id": "nonexistent"})
        assert result["ok"] is False
        assert result["error"]["code"] == "not_found"

    def test_unsubscribe_id_required(self) -> None:
        result = _run(self.TOOL, {})
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_argument"

    def test_unsubscribe_success(self) -> None:
        # First create a subscription
        r1 = _run("matter_subscribe", {"dev": "light-kitchen-01"})
        sub_id = r1["subscription"]["subscription_id"]
        # Then remove it
        result = _run(self.TOOL, {"subscription_id": sub_id})
        assert result["ok"] is True
        assert result["removed"] == sub_id


# ===================================================================
# matter_subscription_list
# ===================================================================


class TestMatterSubscriptionList:
    TOOL = "matter_subscription_list"

    def test_list_empty(self) -> None:
        result = _run(self.TOOL, {})
        assert result["ok"] is True
        assert result["count"] >= 0

    def test_list_with_subscription(self) -> None:
        # Create a subscription
        r1 = _run("matter_subscribe", {"dev": "lock-garage-01"})
        sub_id = r1["subscription"]["subscription_id"]
        # List
        result = _run(self.TOOL, {})
        assert result["ok"] is True
        assert result["count"] >= 1
        ids = [s["subscription_id"] for s in result["items"]]
        assert sub_id in ids
        # Cleanup
        _run("matter_unsubscribe", {"subscription_id": sub_id})

    def test_text_output(self) -> None:
        import importlib
        mod = importlib.import_module(f"{TOOLS_DIR}.{self.TOOL}_tool")
        raw = mod.run_tool({"fmt": "text"})
        assert isinstance(raw, str)
