"""Tests for plugin channels support."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def plugin_with_channels(repo_tmp_path: Path) -> Path:
    """Create a plugin with channels configuration."""
    p = repo_tmp_path / "plugins" / "channel-plugin"
    (p / ".claude-plugin").mkdir(parents=True)
    manifest = {
        "name": "channel-plugin",
        "channels": [
            {
                "server": "telegram",
                "userConfig": {
                    "bot_token": {
                        "type": "string",
                        "title": "Bot Token",
                        "description": "Telegram bot token",
                        "sensitive": True,
                    },
                    "owner_id": {
                        "type": "string",
                        "title": "Owner ID",
                        "description": "Your Telegram user ID",
                    },
                },
            },
            {
                "server": "slack",
                "userConfig": {
                    "webhook_url": {
                        "type": "string",
                        "title": "Webhook URL",
                        "description": "Slack webhook URL",
                    },
                },
            },
        ],
    }
    (p / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return p


class TestChannelsParse:
    """Tests for parsing channels from plugin manifest."""

    def test_parse_channels(self, plugin_with_channels: Path) -> None:
        """Channels should be parseable from plugin.json."""
        from uagent.plugin_shared import parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_channels))
        assert manifest is not None
        channels = manifest.get("channels")
        assert channels is not None
        assert len(channels) == 2
        assert channels[0]["server"] == "telegram"
        assert channels[1]["server"] == "slack"

    def test_channel_userconfig(self, plugin_with_channels: Path) -> None:
        """Channel userConfig should be parseable."""
        from uagent.plugin_shared import parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_channels))
        channels = manifest["channels"]
        uc = channels[0]["userConfig"]
        assert uc["bot_token"]["sensitive"] is True
        assert uc["owner_id"]["type"] == "string"
        assert uc["owner_id"].get("sensitive") is None

    def test_no_channels(self) -> None:
        """No channels field should return empty list."""
        from uagent.plugin_shared import parse_plugin_channels

        channels = parse_plugin_channels({})
        assert channels == []


class TestChannelsStore:
    """Tests for storing channel configurations."""

    def test_store_channel_config(self, repo_tmp_path: Path) -> None:
        """Channel config should be storable."""
        from uagent.plugin_shared import store_channel_config, get_channel_config

        store_path = repo_tmp_path / "channels.json"
        store_path.write_text(json.dumps({"channels": []}), encoding="utf-8")

        store_channel_config(
            "channel-plugin",
            "telegram",
            {"bot_token": "abc123", "owner_id": "user1"},
            store_path=str(store_path),
        )
        config = get_channel_config(
            "channel-plugin", "telegram", store_path=str(store_path)
        )
        assert config is not None
        assert config["bot_token"] == "abc123"
        assert config["owner_id"] == "user1"

    def test_get_nonexistent_channel(self, repo_tmp_path: Path) -> None:
        """Nonexistent channel should return None."""
        from uagent.plugin_shared import get_channel_config

        store_path = repo_tmp_path / "empty_channels.json"
        store_path.write_text(json.dumps({"channels": []}), encoding="utf-8")

        config = get_channel_config(
            "no-plugin", "no-channel", store_path=str(store_path)
        )
        assert config is None

    def test_list_channels(self, repo_tmp_path: Path) -> None:
        """Should list all configured channels."""
        from uagent.plugin_shared import (
            store_channel_config,
            list_channel_configs,
        )

        store_path = repo_tmp_path / "list_channels.json"
        store_path.write_text(json.dumps({"channels": []}), encoding="utf-8")

        store_channel_config("p1", "ch1", {}, store_path=str(store_path))
        store_channel_config("p1", "ch2", {}, store_path=str(store_path))

        channels = list_channel_configs(store_path=str(store_path))
        assert len(channels) == 2
        names = [c["channel"] for c in channels]
        assert "ch1" in names
        assert "ch2" in names

    def test_remove_channel_config(self, repo_tmp_path: Path) -> None:
        """Channel config should be removable."""
        from uagent.plugin_shared import (
            store_channel_config,
            get_channel_config,
            remove_channel_config,
        )

        store_path = repo_tmp_path / "remove_ch.json"
        store_path.write_text(json.dumps({"channels": []}), encoding="utf-8")

        store_channel_config("p1", "ch1", {"key": "val"}, store_path=str(store_path))
        assert get_channel_config("p1", "ch1", store_path=str(store_path)) is not None

        remove_channel_config("p1", "ch1", store_path=str(store_path))
        assert get_channel_config("p1", "ch1", store_path=str(store_path)) is None

    def test_remove_plugin_all_channels(self, repo_tmp_path: Path) -> None:
        """All channels for a plugin should be removable."""
        from uagent.plugin_shared import (
            store_channel_config,
            remove_plugin_channels,
            list_channel_configs,
        )

        store_path = repo_tmp_path / "remove_all.json"
        store_path.write_text(json.dumps({"channels": []}), encoding="utf-8")

        store_channel_config("p1", "ch1", {}, store_path=str(store_path))
        store_channel_config("p1", "ch2", {}, store_path=str(store_path))
        store_channel_config("p2", "ch1", {}, store_path=str(store_path))

        remove_plugin_channels("p1", store_path=str(store_path))

        channels = list_channel_configs(store_path=str(store_path))
        assert len(channels) == 1
        assert channels[0]["channel"] == "ch1"
        assert channels[0]["plugin"] == "p2"
