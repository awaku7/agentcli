"""Tests for userConfig support in plugins."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def plugin_with_userconfig(repo_tmp_path: Path) -> Path:
    """Create a plugin with userConfig."""
    p = repo_tmp_path / "plugins" / "config-plugin"
    (p / ".claude-plugin").mkdir(parents=True)
    manifest = {
        "name": "config-plugin",
        "userConfig": {
            "api_endpoint": {
                "type": "string",
                "title": "API Endpoint",
                "description": "Your API endpoint URL",
                "required": True,
            },
            "api_token": {
                "type": "string",
                "title": "API Token",
                "description": "Authentication token",
                "sensitive": True,
            },
            "max_retries": {
                "type": "number",
                "title": "Max Retries",
                "description": "Maximum retry count",
                "default": 3,
            },
            "debug_mode": {
                "type": "boolean",
                "title": "Debug Mode",
                "description": "Enable debug output",
                "default": False,
            },
        },
    }
    (p / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return p


class TestUserConfigParse:
    """Tests for parsing userConfig from plugin manifest."""

    def test_parse_userconfig(self, plugin_with_userconfig: Path) -> None:
        """userConfig should be parseable from plugin.json."""
        from uagent.plugin_shared import parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_userconfig))
        assert manifest is not None
        uc = manifest.get("userConfig")
        assert uc is not None
        assert "api_endpoint" in uc
        assert "api_token" in uc
        assert "max_retries" in uc
        assert "debug_mode" in uc

    def test_userconfig_field_types(self, plugin_with_userconfig: Path) -> None:
        """userConfig fields should have correct types."""
        from uagent.plugin_shared import parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_userconfig))
        uc = manifest["userConfig"]
        assert uc["api_endpoint"]["type"] == "string"
        assert uc["api_token"]["type"] == "string"
        assert uc["max_retries"]["type"] == "number"
        assert uc["debug_mode"]["type"] == "boolean"

    def test_userconfig_sensitive_flag(self, plugin_with_userconfig: Path) -> None:
        """Sensitive fields should be flagged."""
        from uagent.plugin_shared import parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_userconfig))
        uc = manifest["userConfig"]
        assert uc["api_token"].get("sensitive") is True
        assert uc["api_endpoint"].get("sensitive") is None

    def test_userconfig_defaults(self, plugin_with_userconfig: Path) -> None:
        """Default values should be preserved."""
        from uagent.plugin_shared import parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_userconfig))
        uc = manifest["userConfig"]
        assert uc["max_retries"].get("default") == 3
        assert uc["debug_mode"].get("default") is False


class TestUserConfigStore:
    """Tests for storing userConfig values."""

    def test_store_userconfig_values(self, repo_tmp_path: Path) -> None:
        """userConfig values should be storable in settings."""
        from uagent.plugin_shared import store_user_config_values, get_user_config_values

        settings_path = repo_tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"pluginConfigs": []}), encoding="utf-8")

        values = {
            "api_endpoint": "https://api.example.com",
            "max_retries": 5,
        }
        store_user_config_values(
            "config-plugin",
            values,
            settings_path=str(settings_path),
        )

        stored = get_user_config_values("config-plugin", settings_path=str(settings_path))
        assert stored["api_endpoint"] == "https://api.example.com"
        assert stored["max_retries"] == 5

    def test_get_userconfig_defaults(self, plugin_with_userconfig: Path, repo_tmp_path: Path) -> None:
        """Getting values should fall back to defaults for missing keys."""
        from uagent.plugin_shared import (
            get_user_config_values,
            parse_plugin_manifest,
        )

        manifest = parse_plugin_manifest(str(plugin_with_userconfig))
        assert manifest is not None

        settings_path = repo_tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"pluginConfigs": []}), encoding="utf-8")

        values = get_user_config_values(
            "config-plugin",
            manifest=manifest,
            settings_path=str(settings_path),
        )
        # debug_mode default is False
        assert values.get("debug_mode") is False

    def test_resolve_user_config_in_string(self, repo_tmp_path: Path) -> None:
        """${user_config.KEY} should be resolvable in strings."""
        from uagent.plugin_shared import resolve_user_config_string

        values = {"api_endpoint": "api.example.com", "token": "abc123"}

        result = resolve_user_config_string(
            "https://${user_config.api_endpoint}/v1",
            values,
        )
        assert result == "https://api.example.com/v1"

    def test_resolve_unknown_key(self, repo_tmp_path: Path) -> None:
        """Unknown user_config keys should be left as-is."""
        from uagent.plugin_shared import resolve_user_config_string

        values = {"known_key": "value"}
        result = resolve_user_config_string(
            "${user_config.unknown_key}",
            values,
        )
        assert "${user_config.unknown_key}" in result

    def test_plugin_configs_persistence(self, repo_tmp_path: Path) -> None:
        """Multiple plugins' configs should coexist."""
        from uagent.plugin_shared import store_user_config_values, get_user_config_values

        settings_path = repo_tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"pluginConfigs": []}), encoding="utf-8")

        store_user_config_values("plugin-a", {"key_a": "val_a"}, settings_path=str(settings_path))
        store_user_config_values("plugin-b", {"key_b": "val_b"}, settings_path=str(settings_path))

        a = get_user_config_values("plugin-a", settings_path=str(settings_path))
        b = get_user_config_values("plugin-b", settings_path=str(settings_path))
        assert a["key_a"] == "val_a"
        assert b["key_b"] == "val_b"
        assert "key_b" not in a
        assert "key_a" not in b
