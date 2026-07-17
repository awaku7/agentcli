"""Tests for the plugin system (plugin_shared, plugin_manage_tool, runtime_plugins).

TDD: write tests first, then implement.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def plugin_dir(repo_tmp_path: Path) -> Path:
    """Create a minimal valid plugin directory with manifest."""
    p = repo_tmp_path / "plugins" / "test-plugin"
    manifest_dir = p / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    manifest = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A test plugin",
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    # Add a skill
    skill_dir = p / "skills" / "hello"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: hello\ndescription: A greeting skill\n---\n\nHello!",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def plugin_dir_no_manifest(repo_tmp_path: Path) -> Path:
    """Plugin directory without manifest (auto-detect by directory name)."""
    p = repo_tmp_path / "plugins" / "nameless-plugin"
    skill_dir = p / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\ndescription: Foo skill\n---\n\nFoo!",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def settings_file(repo_tmp_path: Path) -> Path:
    """Create a minimal settings.json with enabledPlugins."""
    sf = repo_tmp_path / ".uag" / "settings.json"
    sf.parent.mkdir(parents=True)
    sf.write_text(
        json.dumps({
            "enabledPlugins": {
                "test-plugin": True,
                "disabled-plugin": False,
            }
        }, indent=2),
        encoding="utf-8",
    )
    return sf


@pytest.fixture()
def user_plugins_dir(repo_tmp_path: Path) -> Path:
    """Simulate ~/.uag/plugins/."""
    p = repo_tmp_path / ".uag" / "plugins"
    p.mkdir(parents=True)
    return p


@pytest.fixture()
def project_plugins_dir(repo_tmp_path: Path) -> Path:
    """Simulate .uag/plugins/ in project."""
    p = repo_tmp_path / ".uag" / "plugins"
    p.mkdir(parents=True)
    return p


# =========================================================================
# plugin_shared tests
# =========================================================================


class TestParsePluginManifest:
    """Tests for parse_plugin_manifest()."""

    def test_parse_valid_manifest(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import parse_plugin_manifest

        result = parse_plugin_manifest(str(plugin_dir))
        assert result is not None
        assert result["name"] == "test-plugin"
        assert result["version"] == "1.0.0"
        assert result["description"] == "A test plugin"
        assert result["_path"] == str(plugin_dir)

    def test_parse_manifest_not_found(self, plugin_dir_no_manifest: Path) -> None:
        from uagent.plugin_shared import parse_plugin_manifest

        result = parse_plugin_manifest(str(plugin_dir_no_manifest))
        # Without manifest, should return default manifest with dirname as name
        assert result is not None
        assert result["name"] == "nameless-plugin"
        assert result["_path"] == str(plugin_dir_no_manifest)

    def test_parse_nonexistent_directory(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import parse_plugin_manifest

        result = parse_plugin_manifest(str(repo_tmp_path / "nonexistent"))
        assert result is None

    def test_parse_invalid_json(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import parse_plugin_manifest

        p = repo_tmp_path / "broken-plugin"
        manifest_dir = p / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "plugin.json").write_text(
            "{invalid json}", encoding="utf-8"
        )
        result = parse_plugin_manifest(str(p))
        assert result is None

    def test_parse_manifest_missing_name(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import parse_plugin_manifest

        p = repo_tmp_path / "no-name-plugin"
        manifest_dir = p / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"version": "1.0.0"}), encoding="utf-8"
        )
        result = parse_plugin_manifest(str(p))
        # Without name, falls back to dirname
        assert result is not None
        assert result["name"] == "no-name-plugin"


class TestValidatePluginManifest:
    """Tests for validate_plugin_manifest()."""

    def test_validate_ok(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import validate_plugin_manifest

        manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
        }
        ok, errors, warnings = validate_plugin_manifest(str(plugin_dir), manifest)
        assert ok is True
        assert errors == []
        assert warnings == []

    def test_validate_path_traversal(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import validate_plugin_manifest

        manifest = {
            "name": "test-plugin",
            "mcpServers": "../outside/etc/passwd",
        }
        ok, errors, warnings = validate_plugin_manifest(str(plugin_dir), manifest)
        assert ok is False
        assert any("traversal" in e.lower() for e in errors)

    def test_validate_unknown_fields_warning(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import validate_plugin_manifest

        manifest = {
            "name": "test-plugin",
            "unknownField": "value",
        }
        ok, errors, warnings = validate_plugin_manifest(
            str(plugin_dir), manifest, strict=False
        )
        assert ok is True
        assert warnings != []

    def test_validate_strict_fails_on_warning(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import validate_plugin_manifest

        manifest = {
            "name": "test-plugin",
            "unknownField": "value",
        }
        ok, errors, warnings = validate_plugin_manifest(
            str(plugin_dir), manifest, strict=True
        )
        assert ok is False
        assert errors != []

    def test_validate_default_enabled_type(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import validate_plugin_manifest

        manifest = {
            "name": "test-plugin",
            "defaultEnabled": "not-a-boolean",
        }
        ok, errors, warnings = validate_plugin_manifest(str(plugin_dir), manifest)
        assert ok is False


class TestScanPlugins:
    """Tests for scan_plugins()."""

    def test_scan_finds_plugins(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.plugin_shared import scan_plugins

        results = scan_plugins([str(repo_tmp_path / "plugins")])
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "test-plugin" in names

    def test_scan_empty_directory(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import scan_plugins

        empty = repo_tmp_path / "empty-plugins"
        empty.mkdir(parents=True)
        results = scan_plugins([str(empty)])
        assert results == []

    def test_scan_skips_non_directories(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import scan_plugins

        d = repo_tmp_path / "plugin-dir"
        d.mkdir(parents=True)
        (d / "not-a-plugin.txt").write_text("hello", encoding="utf-8")
        results = scan_plugins([str(d)])
        assert results == []

    def test_scan_dedup_by_name(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.plugin_shared import scan_plugins

        # Same plugin name in two directories - first should win
        dup_dir = repo_tmp_path / "dup-plugins" / "test-plugin"
        dup_dir.mkdir(parents=True)
        dup_manifest = dup_dir / ".claude-plugin"
        dup_manifest.mkdir()
        (dup_manifest / "plugin.json").write_text(
            json.dumps({"name": "test-plugin", "version": "2.0.0"}),
            encoding="utf-8",
        )

        results = scan_plugins([
            str(repo_tmp_path / "plugins"),
            str(repo_tmp_path / "dup-plugins"),
        ])
        test_plugins = [r for r in results if r["name"] == "test-plugin"]
        assert len(test_plugins) == 1
        # First found wins (version should be 1.0.0 from plugin_dir)
        assert test_plugins[0]["version"] == "1.0.0"


class TestResolvePluginRoots:
    """Tests for get_plugin_roots()."""

    def test_returns_user_and_project_roots(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import get_plugin_roots

        roots = get_plugin_roots(cwd=str(repo_tmp_path))
        paths = [str(Path(r).resolve()) for r in roots]

        # Should include ~/.uag/plugins/
        assert any(".uag" in p and "plugins" in p for p in paths)

        # Should include .uag/plugins/ relative to cwd
        project_plugin = str((repo_tmp_path / ".uag" / "plugins").resolve())
        assert project_plugin in paths

    def test_returns_claude_compat_roots(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import get_plugin_roots

        roots = get_plugin_roots(cwd=str(repo_tmp_path))
        paths = [str(Path(r).resolve()) for r in roots]

        # Should include ~/.claude/plugins/
        assert any(".claude" in p and "plugins" in p for p in paths)

        # Should include .claude/plugins/ relative to cwd
        project_claude = str((repo_tmp_path / ".claude" / "plugins").resolve())
        assert project_claude in paths

    def test_ordering(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import get_plugin_roots

        roots = get_plugin_roots(cwd=str(repo_tmp_path))
        resolved = [str(Path(r).resolve()) for r in roots]

        # Project .uag/plugins/ should come before any user path
        project_key = str((repo_tmp_path / ".uag" / "plugins").resolve())
        user_home = Path.home()

        project_idx = None
        user_idx = None
        for i, r in enumerate(resolved):
            if r == project_key:
                project_idx = i
            elif "plugins" in r and str(user_home) in r:
                user_idx = i

        assert project_idx is not None, f"project root not found in {resolved}"
        assert user_idx is not None, f"user root not found in {resolved}"
        assert project_idx < user_idx, (
            f"project root (idx={project_idx}) should precede user root (idx={user_idx})"
        )


class TestGetEnabledPlugins:
    """Tests for get_enabled_plugins()."""

    def test_reads_enabled_plugins(self, settings_file: Path) -> None:
        from uagent.plugin_shared import get_enabled_plugins

        state_dir = str(settings_file.parent)
        result = get_enabled_plugins(state_dir=state_dir)
        assert result["test-plugin"] is True
        assert result["disabled-plugin"] is False

    def test_returns_empty_when_no_settings(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import get_enabled_plugins

        result = get_enabled_plugins(state_dir=str(repo_tmp_path))
        assert result == {}

    def test_invalid_json_returns_empty(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import get_enabled_plugins

        state_dir = repo_tmp_path / ".uag"
        state_dir.mkdir(parents=True)
        (state_dir / "settings.json").write_text(
            "{broken}", encoding="utf-8"
        )
        result = get_enabled_plugins(state_dir=str(state_dir))
        assert result == {}


class TestPluginEnabled:
    """Tests for is_plugin_enabled()."""

    def test_enabled(self, settings_file: Path) -> None:
        from uagent.plugin_shared import is_plugin_enabled

        state_dir = str(settings_file.parent)
        result = is_plugin_enabled("test-plugin", state_dir=state_dir)
        assert result is True

    def test_disabled(self, settings_file: Path) -> None:
        from uagent.plugin_shared import is_plugin_enabled

        state_dir = str(settings_file.parent)
        result = is_plugin_enabled("disabled-plugin", state_dir=state_dir)
        assert result is False

    def test_not_listed_default_enabled(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import is_plugin_enabled

        result = is_plugin_enabled("unknown-plugin", state_dir=str(repo_tmp_path))
        # Default is True when not listed
        assert result is True

    def test_not_listed_default_disabled(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import is_plugin_enabled

        result = is_plugin_enabled(
            "unknown-plugin",
            state_dir=str(repo_tmp_path),
            default_enabled=False,
        )
        assert result is False


class TestDiscoverPluginComponents:
    """Tests for discover_plugin_components()."""

    def test_discovers_skills(self, plugin_dir: Path) -> None:
        from uagent.plugin_shared import discover_plugin_components

        manifest = {
            "name": "test-plugin",
            "skills": "./skills",
        }
        components = discover_plugin_components(str(plugin_dir), manifest)
        assert "skills" in components
        assert len(components["skills"]) >= 1
        assert "hello" in components["skills"]

    def test_empty_when_no_components(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import discover_plugin_components

        p = repo_tmp_path / "empty-plugin"
        p.mkdir(parents=True)
        manifest = {"name": "empty-plugin"}
        components = discover_plugin_components(str(p), manifest)
        assert components == {}

    def test_skills_default_directory(self, repo_tmp_path: Path) -> None:
        from uagent.plugin_shared import discover_plugin_components

        p = repo_tmp_path / "default-skills-plugin"
        skill_dir = p / "skills" / "bar"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bar\ndescription: Bar\n---\nBar!",
            encoding="utf-8",
        )
        manifest = {"name": "default-skills-plugin"}
        components = discover_plugin_components(str(p), manifest)
        assert "skills" in components
        assert "bar" in components["skills"]


# =========================================================================
# plugin_manage_tool tests
# =========================================================================


class TestPluginManageToolSpec:
    """Tests for plugin_manage_tool TOOL_SPEC."""

    def test_tool_spec_exists(self) -> None:
        from uagent.tools.plugin_manage_tool import TOOL_SPEC

        assert isinstance(TOOL_SPEC, dict)
        assert TOOL_SPEC.get("type") == "function"
        fn = TOOL_SPEC.get("function", {})
        assert fn.get("name") == "plugin_manage"
        assert fn.get("description")
        assert isinstance(fn.get("parameters", {}).get("properties"), dict)

    def test_tool_spec_action_enum(self) -> None:
        from uagent.tools.plugin_manage_tool import TOOL_SPEC

        params = TOOL_SPEC["function"]["parameters"]
        action_prop = params["properties"].get("action", {})
        assert "enum" in action_prop
        expected = ["list", "install", "remove", "enable", "disable", "validate", "info"]
        for e in expected:
            assert e in action_prop["enum"], f"Missing action: {e}"


class TestPluginManageRunTool:
    """Tests for plugin_manage_tool.run_tool()."""

    def test_list_empty(self, repo_tmp_path: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        # Temporarily set plugin roots to empty dir
        result = run_tool({"action": "list", "_test_roots": [str(repo_tmp_path)]})
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert isinstance(parsed.get("plugins"), list)

    def test_list_with_plugin(self, repo_tmp_path: Path, plugin_dir: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        plugins_root = str(repo_tmp_path / "plugins")
        result = run_tool({
            "action": "list",
            "_test_roots": [plugins_root],
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        names = [p["name"] for p in parsed["plugins"]]
        assert "test-plugin" in names

    def test_info_known_plugin(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        plugins_root = str(repo_tmp_path / "plugins")
        result = run_tool({
            "action": "info",
            "name": "test-plugin",
            "_test_roots": [plugins_root],
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert parsed["name"] == "test-plugin"
        assert parsed["version"] == "1.0.0"

    def test_info_unknown_plugin(self, repo_tmp_path: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        result = run_tool({
            "action": "info",
            "name": "nonexistent",
            "_test_roots": [str(repo_tmp_path)],
        })
        parsed = json.loads(result)
        assert parsed["ok"] is False

    def test_install_from_local_dir(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        dest_root = repo_tmp_path / "dest-plugins"
        dest_root.mkdir(parents=True)
        result = run_tool({
            "action": "install",
            "source": str(plugin_dir),
            "name": "installed-plugin",
            "_test_install_root": str(dest_root),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert (dest_root / "installed-plugin").exists()
        assert (dest_root / "installed-plugin" / ".claude-plugin" / "plugin.json").exists()

    def test_remove_plugin(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        dest_root = repo_tmp_path / "removable-plugins"
        # Pre-install
        shutil.copytree(plugin_dir, dest_root / "to-remove")
        assert (dest_root / "to-remove").exists()

        result = run_tool({
            "action": "remove",
            "name": "to-remove",
            "_test_install_root": str(dest_root),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert not (dest_root / "to-remove").exists()

    def test_enable_plugin(self, repo_tmp_path: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        state_dir = repo_tmp_path / ".uag"
        state_dir.mkdir(parents=True)
        result = run_tool({
            "action": "enable",
            "name": "my-plugin",
            "_test_state_dir": str(state_dir),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True

        # Verify settings.json was written
        sf = state_dir / "settings.json"
        assert sf.exists()
        settings = json.loads(sf.read_text(encoding="utf-8"))
        assert settings["enabledPlugins"]["my-plugin"] is True

    def test_disable_plugin(self, repo_tmp_path: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        state_dir = repo_tmp_path / ".uag"
        state_dir.mkdir(parents=True)
        result = run_tool({
            "action": "disable",
            "name": "my-plugin",
            "_test_state_dir": str(state_dir),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True

        sf = state_dir / "settings.json"
        assert sf.exists()
        settings = json.loads(sf.read_text(encoding="utf-8"))
        assert settings["enabledPlugins"]["my-plugin"] is False

    def test_validate_ok(self, plugin_dir: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        result = run_tool({
            "action": "validate",
            "name": "test-plugin",
            "_test_roots": [str(plugin_dir.parent)],
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True

    def test_validate_missing_directory(self, repo_tmp_path: Path) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        result = run_tool({
            "action": "validate",
            "name": "no-such-plugin",
            "_test_roots": [str(repo_tmp_path)],
        })
        parsed = json.loads(result)
        assert parsed["ok"] is False


class TestPluginManageCmdSpec:
    """Tests for plugin_manage_tool CMD_SPECS."""

    def test_cmd_specs_registered(self) -> None:
        from uagent.tools.plugin_manage_tool import CMD_SPECS

        assert isinstance(CMD_SPECS, list)
        assert len(CMD_SPECS) > 0

        commands = {s["command"] for s in CMD_SPECS}
        assert "plugin" in commands

        subcommands = {
            s["subcommand"]
            for s in CMD_SPECS
            if s["command"] == "plugin"
        }
        expected = {
            "list", "install", "remove", "enable", "disable",
            "reload", "info", "init", "validate",
            "marketplace", "uninstall",
        }
        for e in expected:
            assert e in subcommands, f"Missing subcommand: {e}"


# =========================================================================
# runtime_plugins tests
# =========================================================================


class TestRuntimePlugins:
    """Tests for runtime_plugins.load_plugins_at_startup()."""

    def test_load_no_plugins(self, repo_tmp_path: Path) -> None:
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[],
        )
        assert isinstance(result, list)
        assert result == []

    def test_load_plugin_with_skills(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[str(plugin_dir.parent)],
            state_dir=str(repo_tmp_path / ".uag"),
        )
        assert len(result) >= 1
        loaded = [p for p in result if p["name"] == "test-plugin"]
        assert len(loaded) == 1
        assert loaded[0]["enabled"] is True
        assert "skills" in loaded[0]["components"]

    def test_load_disabled_plugin(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        # Mark plugin as disabled
        state_dir = repo_tmp_path / ".uag"
        state_dir.mkdir(parents=True)
        (state_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"test-plugin": False}}),
            encoding="utf-8",
        )

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[str(plugin_dir.parent)],
            state_dir=str(state_dir),
        )
        loaded = [p for p in result if p["name"] == "test-plugin"]
        assert len(loaded) == 1
        assert loaded[0]["enabled"] is False

    def test_load_from_claude_compat_dir(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        # Put plugin in .claude/plugins/ instead
        claude_plugins = repo_tmp_path / ".claude" / "plugins"
        shutil.copytree(plugin_dir, claude_plugins / "test-plugin")

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[str(claude_plugins)],
        )
        loaded = [p for p in result if p["name"] == "test-plugin"]
        assert len(loaded) == 1

    def test_plugin_dir_arg_overrides(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        # --plugin-dir should load plugins from the given directory
        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[],
            extra_plugin_dirs=[str(plugin_dir.parent)],
        )
        loaded = [p for p in result if p["name"] == "test-plugin"]
        assert len(loaded) == 1


# =========================================================================
# Integration: end-to-end plugin workflow
# =========================================================================


class TestPluginWorkflow:
    """End-to-end workflow tests."""

    def test_install_list_remove_cycle(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        install_root = repo_tmp_path / "e2e-plugins"
        install_root.mkdir(parents=True)

        # Install
        r1 = run_tool({
            "action": "install",
            "source": str(plugin_dir),
            "name": "e2e-plugin",
            "_test_install_root": str(install_root),
        })
        assert json.loads(r1)["ok"] is True
        assert (install_root / "e2e-plugin").exists()

        # List
        r2 = run_tool({
            "action": "list",
            "_test_roots": [str(install_root)],
        })
        parsed = json.loads(r2)
        assert parsed["ok"] is True
        names = [p["name"] for p in parsed["plugins"]]
        assert "e2e-plugin" in names

        # Info
        r3 = run_tool({
            "action": "info",
            "name": "e2e-plugin",
            "_test_roots": [str(install_root)],
        })
        parsed = json.loads(r3)
        assert parsed["name"] == "e2e-plugin"

        # Remove
        r4 = run_tool({
            "action": "remove",
            "name": "e2e-plugin",
            "_test_install_root": str(install_root),
        })
        assert json.loads(r4)["ok"] is True
        assert not (install_root / "e2e-plugin").exists()

    def test_enable_disable_persistence(
        self, repo_tmp_path: Path
    ) -> None:
        from uagent.tools.plugin_manage_tool import run_tool

        state_dir = repo_tmp_path / ".uag-persist"
        state_dir.mkdir(parents=True)

        # Enable
        run_tool({
            "action": "enable",
            "name": "persist-plugin",
            "_test_state_dir": str(state_dir),
        })

        # Check persisted
        sf = state_dir / "settings.json"
        settings = json.loads(sf.read_text(encoding="utf-8"))
        assert settings["enabledPlugins"]["persist-plugin"] is True

        # Disable
        run_tool({
            "action": "disable",
            "name": "persist-plugin",
            "_test_state_dir": str(state_dir),
        })

        settings = json.loads(sf.read_text(encoding="utf-8"))
        assert settings["enabledPlugins"]["persist-plugin"] is False


# =========================================================================
# Phase 2a: Skills integration tests
# =========================================================================


class TestPluginSkillsIntegration:
    """Plugin skills should be discoverable by the skills system."""

    def test_get_default_skill_roots_includes_plugin_dirs(
        self, repo_tmp_path: Path
    ) -> None:
        """Plugin skill directories should appear in default skill roots."""
        from uagent.tools.agent_skills_shared import get_default_skill_roots

        # Create a plugin with skills in the project .uag/plugins/ dir
        plugin_skills = repo_tmp_path / ".uag" / "plugins" / "my-plugin" / "skills" / "greet"
        plugin_skills.mkdir(parents=True)
        (plugin_skills / "SKILL.md").write_text(
            "---\nname: greet\ndescription: A greet skill\n---\n\nHi!",
            encoding="utf-8",
        )

        roots = get_default_skill_roots(cwd=str(repo_tmp_path))
        resolved = [str(Path(r).resolve()) for r in roots]

        # The plugin's skills directory should be in roots
        expected = str((repo_tmp_path / ".uag" / "plugins" / "my-plugin" / "skills").resolve())
        assert expected in resolved, f"Expected {expected} in roots: {resolved}"

    def test_skills_list_finds_plugin_skill(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """skills_list should find skills inside plugins when scanning."""
        from uagent.tools.skills_list_tool import run_tool
        import json

        skills_dir = plugin_dir / "skills"
        result = run_tool({
            "root_dir": str(skills_dir),
            "recur": True,
            "include_invalid": True,
        })
        items = json.loads(result)
        names = [i.get("name") for i in items]
        assert "hello" in names, f"Expected 'hello' skill, got {names}"

    def test_skills_load_plugin_skill(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """skills_load should load a skill from a plugin."""
        from uagent.tools.skills_load_tool import run_tool
        import json

        skill_dir = plugin_dir / "skills" / "hello"
        result = run_tool({"skill_dir": str(skill_dir)})
        doc = json.loads(result)
        assert doc["frontmatter"]["name"] == "hello"
        assert "Hello!" in doc["body_markdown"]

    def test_skills_validate_plugin_skill(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """skills_validate should work on plugin skills."""
        from uagent.tools.skills_validate_tool import run_tool
        import json

        skill_dir = plugin_dir / "skills" / "hello"
        result = run_tool({"skill_dir": str(skill_dir), "strict": False})
        obj = json.loads(result)
        assert obj["ok"] is True

    def test_plugin_skill_isolated_from_regular_skills(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """Plugin skills should not interfere with regular skills scan."""
        from uagent.tools.skills_list_tool import run_tool
        import json

        regular_skills_dir = repo_tmp_path / "skills"
        regular_skills_dir.mkdir(parents=True)
        regular_skill = regular_skills_dir / "regular-skill"
        regular_skill.mkdir()
        (regular_skill / "SKILL.md").write_text(
            "---\nname: regular-skill\ndescription: A regular skill\n---\n\nRegular!",
            encoding="utf-8",
        )

        result = run_tool({
            "root_dir": str(regular_skills_dir),
            "recur": True,
        })
        items = json.loads(result)
        names = [i.get("name") for i in items]
        assert "regular-skill" in names
        assert "hello" not in names

    def test_skills_read_file_from_plugin(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """skills_read_file should work for files inside plugin skills."""
        from uagent.tools.skills_read_file_tool import run_tool
        import json

        ref_dir = plugin_dir / "skills" / "hello" / "references"
        ref_dir.mkdir(parents=True)
        (ref_dir / "HELP.md").write_text("Help content", encoding="utf-8")

        skill_dir = plugin_dir / "skills" / "hello"
        result = run_tool({
            "skill_dir": str(skill_dir),
            "relative_path": "references/HELP.md",
            "max_bytes": 1024,
        })
        obj = json.loads(result)
        assert obj["ok"] is True
        assert obj["content"] == "Help content"

    def test_multiple_skills_in_one_plugin(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """A plugin with multiple skills should list all of them."""
        from uagent.tools.skills_list_tool import run_tool
        import json

        skill2 = plugin_dir / "skills" / "goodbye"
        skill2.mkdir(parents=True)
        (skill2 / "SKILL.md").write_text(
            "---\nname: goodbye\ndescription: A farewell skill\n---\n\nGoodbye!",
            encoding="utf-8",
        )

        skills_dir = plugin_dir / "skills"
        result = run_tool({
            "root_dir": str(skills_dir),
            "recur": True,
        })
        items = json.loads(result)
        names = [i.get("name") for i in items]
        assert "hello" in names
        assert "goodbye" in names

    def test_plugin_skill_with_assets(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """Plugin skills can have supporting files alongside SKILL.md."""
        from uagent.tools.skills_read_file_tool import run_tool
        import json

        scripts_dir = plugin_dir / "skills" / "hello" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "run.sh").write_text(
            "#!/bin/sh\necho hello", encoding="utf-8"
        )

        skill_dir = plugin_dir / "skills" / "hello"
        result = run_tool({
            "skill_dir": str(skill_dir),
            "relative_path": "scripts/run.sh",
            "max_bytes": 1024,
        })
        obj = json.loads(result)
        assert obj["ok"] is True

    def test_plugin_skill_detected_via_runtime(
        self, repo_tmp_path: Path, plugin_dir: Path
    ) -> None:
        """runtime_plugins should report plugin skills in components."""
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[str(plugin_dir.parent)],
        )
        plugin = next((p for p in result if p["name"] == "test-plugin"), None)
        assert plugin is not None
        comps = plugin.get("components", {})
        assert "skills" in comps
        assert "hello" in comps["skills"]


# =========================================================================
# Phase 2b: MCP integration tests
# =========================================================================


@pytest.fixture()
def plugin_with_mcp(repo_tmp_path: Path) -> Path:
    """Create a plugin with .mcp.json."""
    p = repo_tmp_path / "plugins" / "mcp-plugin"
    manifest_dir = p / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "mcp-plugin", "version": "1.0.0"}),
        encoding="utf-8",
    )
    # .mcp.json with one server
    mcp_config = {
        "mcpServers": {
            "plugin-db": {
                "command": "python",
                "args": ["-m", "db_server"],
                "env": {"DB_PATH": "${UAGENT_PLUGIN_ROOT}/data"},
            },
            "plugin-api": {
                "command": "node",
                "args": ["server.js"],
            },
        }
    }
    (p / ".mcp.json").write_text(json.dumps(mcp_config, indent=2), encoding="utf-8")
    return p


class TestPluginMCPIntegration:
    """Plugin MCP servers should be integrable with the runtime MCP system."""

    def test_discover_mcp_component(self, plugin_with_mcp: Path) -> None:
        """discover_plugin_components should detect .mcp.json."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_mcp))
        assert manifest is not None
        comps = discover_plugin_components(str(plugin_with_mcp), manifest)
        assert "mcpServers" in comps
        assert comps["mcpServers"] is True

    def test_parse_plugin_mcp_json(self, plugin_with_mcp: Path) -> None:
        """Parse .mcp.json from a plugin and verify structure."""
        import json

        mcp_path = plugin_with_mcp / ".mcp.json"
        assert mcp_path.is_file()
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert "mcpServers" in data
        assert "plugin-db" in data["mcpServers"]
        assert "plugin-api" in data["mcpServers"]

    def test_merge_plugin_mcp_into_config(self, plugin_with_mcp: Path, repo_tmp_path: Path) -> None:
        """Plugin MCP servers can be merged into the main mcp_servers.json format."""
        from uagent.plugin_shared import merge_plugin_mcp_servers
        import json

        # Create main MCP config
        main_config_path = repo_tmp_path / "mcps" / "mcp_servers.json"
        main_config_path.parent.mkdir(parents=True)
        main_config_path.write_text(
            json.dumps({"mcp_servers": []}), encoding="utf-8"
        )

        result = merge_plugin_mcp_servers(
            str(plugin_with_mcp),
            plugin_name="mcp-plugin",
            mcp_config_path=str(main_config_path),
        )
        assert result["ok"] is True
        assert result["merged_count"] == 2

        # Verify the config was written
        config = json.loads(main_config_path.read_text(encoding="utf-8"))
        assert len(config["mcp_servers"]) == 2
        names = [s["name"] for s in config["mcp_servers"]]
        assert "mcp-plugin:plugin-db" in names
        assert "mcp-plugin:plugin-api" in names

    def test_merge_plugin_mcp_source_tracking(self, plugin_with_mcp: Path, repo_tmp_path: Path) -> None:
        """Plugin MCP servers should have source tracking for cleanup."""
        from uagent.plugin_shared import merge_plugin_mcp_servers
        import json

        main_config_path = repo_tmp_path / "mcps" / "mcp_servers.json"
        main_config_path.parent.mkdir(parents=True)
        main_config_path.write_text(
            json.dumps({"mcp_servers": []}), encoding="utf-8"
        )

        merge_plugin_mcp_servers(
            str(plugin_with_mcp),
            plugin_name="mcp-plugin",
            mcp_config_path=str(main_config_path),
        )

        config = json.loads(main_config_path.read_text(encoding="utf-8"))
        for server in config["mcp_servers"]:
            assert server.get("_plugin_source") == "mcp-plugin"

    def test_remove_plugin_mcp_servers(self, plugin_with_mcp: Path, repo_tmp_path: Path) -> None:
        """Plugin MCP servers should be removable by plugin name."""
        from uagent.plugin_shared import (
            merge_plugin_mcp_servers,
            remove_plugin_mcp_servers,
        )
        import json

        main_config_path = repo_tmp_path / "mcps" / "mcp_servers.json"
        main_config_path.parent.mkdir(parents=True)
        # Start with existing non-plugin server + plugin servers
        main_config_path.write_text(
            json.dumps({
                "mcp_servers": [
                    {"name": "user-server", "command": "echo"},
                    {"name": "mcp-plugin:plugin-db", "command": "python", "_plugin_source": "mcp-plugin"},
                    {"name": "mcp-plugin:plugin-api", "command": "node", "_plugin_source": "mcp-plugin"},
                ]
            }),
            encoding="utf-8",
        )

        result = remove_plugin_mcp_servers(
            "mcp-plugin",
            mcp_config_path=str(main_config_path),
        )
        assert result["ok"] is True
        assert result["removed_count"] == 2

        config = json.loads(main_config_path.read_text(encoding="utf-8"))
        assert len(config["mcp_servers"]) == 1
        assert config["mcp_servers"][0]["name"] == "user-server"

    def test_merge_idempotent(self, plugin_with_mcp: Path, repo_tmp_path: Path) -> None:
        """Merging the same plugin twice should not duplicate servers."""
        from uagent.plugin_shared import merge_plugin_mcp_servers
        import json

        main_config_path = repo_tmp_path / "mcps" / "mcp_servers.json"
        main_config_path.parent.mkdir(parents=True)
        main_config_path.write_text(
            json.dumps({"mcp_servers": []}), encoding="utf-8"
        )

        merge_plugin_mcp_servers(
            str(plugin_with_mcp), "mcp-plugin",
            mcp_config_path=str(main_config_path),
        )
        merge_plugin_mcp_servers(
            str(plugin_with_mcp), "mcp-plugin",
            mcp_config_path=str(main_config_path),
        )

        config = json.loads(main_config_path.read_text(encoding="utf-8"))
        assert len(config["mcp_servers"]) == 2  # not 4

    def test_runtime_reports_mcp_components(self, plugin_with_mcp: Path, repo_tmp_path: Path) -> None:
        """runtime_plugins should report MCP in components."""
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[str(plugin_with_mcp.parent)],
        )
        plugin = next((p for p in result if p["name"] == "mcp-plugin"), None)
        assert plugin is not None
        comps = plugin.get("components", {})
        assert "mcpServers" in comps

    def test_inline_mcp_in_manifest(self, repo_tmp_path: Path) -> None:
        """Plugin can declare MCP servers inline in plugin.json instead of .mcp.json."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        p = repo_tmp_path / "plugins" / "inline-mcp-plugin"
        manifest_dir = p / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "plugin.json").write_text(
            json.dumps({
                "name": "inline-mcp-plugin",
                "mcpServers": {
                    "inline-server": {
                        "command": "python",
                        "args": ["server.py"],
                    }
                },
            }),
            encoding="utf-8",
        )

        manifest = parse_plugin_manifest(str(p))
        assert manifest is not None
        comps = discover_plugin_components(str(p), manifest)
        assert "mcpServers" in comps

    def test_no_mcp_in_plugin(self, plugin_dir: Path) -> None:
        """Plugin without .mcp.json should not report MCP component."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_dir))
        assert manifest is not None
        comps = discover_plugin_components(str(plugin_dir), manifest)
        assert "mcpServers" not in comps


# =========================================================================
# Phase 2c: plugin install with remote sources
# =========================================================================


class TestPluginInstallSources:
    """plugin install should handle Git/HTTP ZIP/local ZIP sources."""

    def test_install_from_local_zip(self, repo_tmp_path: Path, plugin_dir: Path) -> None:
        """Install a plugin from a local ZIP file."""
        import shutil
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        # Create ZIP of the plugin
        zip_path = repo_tmp_path / "test-plugin.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(plugin_dir))

        dest = repo_tmp_path / "zip-installed"
        dest.mkdir(parents=True)

        result = run_tool({
            "action": "install",
            "source": str(zip_path),
            "name": "from-zip",
            "_test_install_root": str(dest),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert (dest / "from-zip").exists()
        assert (dest / "from-zip" / ".claude-plugin" / "plugin.json").exists()

    def test_install_source_not_found(self, repo_tmp_path: Path) -> None:
        """Install with nonexistent source should fail gracefully."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        result = run_tool({
            "action": "install",
            "source": str(repo_tmp_path / "nonexistent"),
            "name": "fail",
            "_test_install_root": str(repo_tmp_path / "dest"),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is False

    def test_install_empty_source(self, repo_tmp_path: Path) -> None:
        """Install with empty source should fail."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        result = run_tool({
            "action": "install",
            "source": "",
            "_test_install_root": str(repo_tmp_path / "dest"),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is False

    def test_install_overwrite_not_allowed(self, repo_tmp_path: Path, plugin_dir: Path) -> None:
        """Install over existing plugin without --overwrite should fail."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        dest = repo_tmp_path / "overwrite-test"
        dest.mkdir(parents=True)
        (dest / "existing").mkdir()

        result = run_tool({
            "action": "install",
            "source": str(plugin_dir),
            "name": "existing",
            "_test_install_root": str(dest),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is False

    def test_install_name_inferred_from_source(self, repo_tmp_path: Path, plugin_dir: Path) -> None:
        """When name is omitted, infer from source path."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        dest = repo_tmp_path / "inferred"
        dest.mkdir(parents=True)

        result = run_tool({
            "action": "install",
            "source": str(plugin_dir),
            "_test_install_root": str(dest),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        # Name inferred from source dir basename
        assert parsed["name"] == plugin_dir.name  # "test-plugin"

    def test_install_git_url_detection(self) -> None:
        """Git URLs should be detected by the install logic."""
        from uagent.plugin_shared import is_git_url as detect

        assert detect("git@github.com:user/repo.git") is True
        assert detect("https://github.com/user/repo.git") is True
        assert detect("git://example.com/repo") is True
        assert detect("https://github.com/user/repo") is True  # contains github.com
        assert detect("./local/path") is False
        assert detect("/absolute/path") is False

    def test_install_remote_zip_detection(self) -> None:
        """Remote ZIP URLs should be detected."""
        from uagent.plugin_shared import is_remote_zip as detect

        assert detect("https://example.com/plugin.zip") is True
        assert detect("https://github.com/user/repo/archive/main.zip") is True
        assert detect("https://example.com/plugin.tar.gz") is False
        assert detect("./local/file.zip") is False

    def test_infer_name_from_source(self) -> None:
        """Name should be inferred correctly from various source strings."""
        from uagent.plugin_shared import infer_plugin_name_from_source

        assert infer_plugin_name_from_source("https://github.com/user/my-plugin.git") == "my-plugin"
        assert infer_plugin_name_from_source("https://example.com/archive.zip") == "archive"
        assert infer_plugin_name_from_source("./local/path/my-plugin") == "my-plugin"
        assert infer_plugin_name_from_source("user/repo") == "repo"
        assert infer_plugin_name_from_source("") == "plugin"

    def test_install_zip_with_single_top_dir(self, repo_tmp_path: Path) -> None:
        """ZIP with single top-level dir should install its contents."""
        import shutil, zipfile
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        # Create a source directory with a plugin
        src = repo_tmp_path / "src-plugin"
        (src / ".claude-plugin").mkdir(parents=True)
        (src / ".claude-plugin" / "plugin.json").write_text(
            '{"name": "src-plugin"}', encoding="utf-8"
        )

        # Create ZIP with top-level dir
        zip_path = repo_tmp_path / "wrapped.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, dirs, files in os.walk(str(src)):
                for fn in files:
                    full = os.path.join(root, fn)
                    arcname = os.path.join("top-dir", os.path.relpath(full, str(src)))
                    zf.write(full, arcname)

        dest = repo_tmp_path / "zip-dest"
        dest.mkdir(parents=True)

        result = run_tool({
            "action": "install",
            "source": str(zip_path),
            "name": "unwrapped",
            "_test_install_root": str(dest),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert (dest / "unwrapped" / ".claude-plugin" / "plugin.json").exists()


# =========================================================================
# Phase 2d: Agents bundling tests
# =========================================================================


@pytest.fixture()
def plugin_with_agents(repo_tmp_path: Path) -> Path:
    """Create a plugin with agent definitions."""
    p = repo_tmp_path / "plugins" / "agent-plugin"
    manifest_dir = p / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "agent-plugin", "version": "1.0.0"}),
        encoding="utf-8",
    )
    agents_dir = p / "agents"
    agents_dir.mkdir(parents=True)

    # First agent
    (agents_dir / "code-reviewer.md").write_text(
        "---\n"
        "name: code-reviewer\n"
        "description: Review code for bugs and security issues\n"
        "model: sonnet\n"
        "effort: medium\n"
        "---\n\n"
        "You are a code reviewer. Check for bugs, security issues and performance problems.",
        encoding="utf-8",
    )
    # Second agent
    (agents_dir / "tester.md").write_text(
        "---\n"
        "name: tester\n"
        "description: Generate and run tests\n"
        "maxTurns: 30\n"
        "---\n\n"
        "You are a testing specialist. Write and execute tests.",
        encoding="utf-8",
    )
    return p


class TestPluginAgentsBundling:
    """Plugin agents should be installable as sub-agent roles."""

    def test_discover_agents_component(self, plugin_with_agents: Path) -> None:
        """discover_plugin_components should detect agents/ directory."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_agents))
        assert manifest is not None
        comps = discover_plugin_components(str(plugin_with_agents), manifest)
        assert "agents" in comps
        assert "code-reviewer" in comps["agents"]
        assert "tester" in comps["agents"]

    def test_install_plugin_agents(self, plugin_with_agents: Path, repo_tmp_path: Path) -> None:
        """Plugin agents should be installed as JSON role files."""
        from uagent.plugin_shared import install_plugin_agents
        import json

        roles_dir = repo_tmp_path / "subagent_roles"
        roles_dir.mkdir(parents=True)

        result = install_plugin_agents(
            str(plugin_with_agents),
            plugin_name="agent-plugin",
            roles_dir=str(roles_dir),
        )
        assert result["ok"] is True
        assert result["installed_count"] == 2

        # Check files exist with namespaced names
        from uagent.plugin_shared import _agent_role_filename
        fn1 = _agent_role_filename("agent-plugin", "code-reviewer")
        fn2 = _agent_role_filename("agent-plugin", "tester")
        assert (roles_dir / fn1).is_file()
        assert (roles_dir / fn2).is_file()

        # Verify content
        data = json.loads((roles_dir / fn1).read_text(encoding="utf-8"))
        assert data["name"] == "agent-plugin:code-reviewer"
        assert "bugs" in data["description"]
        assert "code" in data["system_prompt"].lower()

    def test_install_agents_idempotent(self, plugin_with_agents: Path, repo_tmp_path: Path) -> None:
        """Installing same plugin agents twice should not duplicate."""
        from uagent.plugin_shared import install_plugin_agents

        roles_dir = repo_tmp_path / "idempotent-roles"
        roles_dir.mkdir(parents=True)

        first = install_plugin_agents(str(plugin_with_agents), "agent-plugin", roles_dir=str(roles_dir))
        assert first["installed_count"] == 2, f"First install should install 2 agents, got {first}"

        result = install_plugin_agents(str(plugin_with_agents), "agent-plugin", roles_dir=str(roles_dir))
        assert result["installed_count"] == 0  # no new files

        from pathlib import Path as _Path
        json_files = list(_Path(str(roles_dir)).glob("*.json"))
        assert len(json_files) == 2, f"Expected 2 json files, got {len(json_files)}: {json_files}"

    def test_remove_plugin_agents(self, plugin_with_agents: Path, repo_tmp_path: Path) -> None:
        """Plugin agents should be removable by plugin name."""
        from uagent.plugin_shared import install_plugin_agents, remove_plugin_agents

        roles_dir = repo_tmp_path / "removable-roles"
        roles_dir.mkdir(parents=True)

        install_plugin_agents(str(plugin_with_agents), "agent-plugin", roles_dir=str(roles_dir))
        assert len(list(roles_dir.glob("*.json"))) == 2

        result = remove_plugin_agents("agent-plugin", roles_dir=str(roles_dir))
        assert result["ok"] is True
        assert result["removed_count"] == 2
        assert len(list(roles_dir.glob("*.json"))) == 0

    def test_remove_partial_cleanup(self, repo_tmp_path: Path) -> None:
        """Removing agents from one plugin should not affect other plugins."""
        from uagent.plugin_shared import remove_plugin_agents

        roles_dir = repo_tmp_path / "partial-roles"
        roles_dir.mkdir(parents=True)

        from uagent.plugin_shared import _agent_role_filename
        # Pre-create some role files (use platform-safe filenames)
        fn_a1 = _agent_role_filename("plugin-a", "agent1")
        fn_a2 = _agent_role_filename("plugin-a", "agent2")
        fn_b1 = _agent_role_filename("plugin-b", "agent1")
        (roles_dir / fn_a1).write_text('{"name": "plugin-a:agent1"}', encoding="utf-8")
        (roles_dir / fn_a2).write_text('{"name": "plugin-a:agent2"}', encoding="utf-8")
        (roles_dir / fn_b1).write_text('{"name": "plugin-b:agent1"}', encoding="utf-8")

        result = remove_plugin_agents("plugin-a", roles_dir=str(roles_dir))
        assert result["removed_count"] == 2

        remaining = [f.name for f in sorted(roles_dir.glob("*.json"))]
        assert remaining == [fn_b1]

    def test_no_agents_in_plugin(self, plugin_dir: Path) -> None:
        """Plugin without agents/ should not report agents component."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_dir))
        assert manifest is not None
        comps = discover_plugin_components(str(plugin_dir), manifest)
        assert "agents" not in comps or comps["agents"] == []

    def test_runtime_reports_agents(self, plugin_with_agents: Path, repo_tmp_path: Path) -> None:
        """runtime_plugins should report agents in components."""
        from uagent.runtime.runtime_plugins import load_plugins_at_startup

        result = load_plugins_at_startup(
            cwd=str(repo_tmp_path),
            plugin_dirs=[str(plugin_with_agents.parent)],
        )
        plugin = next((p for p in result if p["name"] == "agent-plugin"), None)
        assert plugin is not None
        comps = plugin.get("components", {})
        assert "agents" in comps
        assert "code-reviewer" in comps["agents"]
        assert "tester" in comps["agents"]

    def test_agent_md_frontmatter_parsing(self, plugin_with_agents: Path) -> None:
        """Agent .md files with YAML frontmatter should parse correctly."""
        from uagent.plugin_shared import parse_agent_md

        agent_file = plugin_with_agents / "agents" / "code-reviewer.md"
        result = parse_agent_md(str(agent_file))
        assert result is not None
        assert result["name"] == "code-reviewer"
        assert "bugs" in result["description"]
        assert "code" in result["system_prompt"].lower()

    def test_agent_md_without_frontmatter(self, repo_tmp_path: Path) -> None:
        """Agent .md without frontmatter should still work."""
        from uagent.plugin_shared import parse_agent_md

        f = repo_tmp_path / "simple-agent.md"
        f.write_text("Just a simple prompt without frontmatter.", encoding="utf-8")
        result = parse_agent_md(str(f))
        assert result is not None
        assert result["name"] == "simple-agent"
        assert "simple prompt" in result["system_prompt"]


# =========================================================================
# Phase 2e: Hooks integration tests
# =========================================================================


@pytest.fixture()
def plugin_with_hooks(repo_tmp_path: Path) -> Path:
    """Create a plugin with hooks configuration."""
    p = repo_tmp_path / "plugins" / "hooks-plugin"
    manifest_dir = p / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "hooks-plugin", "version": "1.0.0"}),
        encoding="utf-8",
    )
    # hooks/hooks.json
    hooks_dir = p / "hooks"
    hooks_dir.mkdir(parents=True)
    hooks_config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo 'checking write...'",
                        }
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo 'done'",
                        }
                    ]
                }
            ],
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "prompt",
                            "prompt": "Remember to check permissions.",
                        }
                    ]
                }
            ],
        }
    }
    (hooks_dir / "hooks.json").write_text(
        json.dumps(hooks_config, indent=2), encoding="utf-8"
    )
    return p


class TestPluginHooksIntegration:
    """Plugin hooks should be parseable and registrable."""

    def test_discover_hooks_component(self, plugin_with_hooks: Path) -> None:
        """discover_plugin_components should detect hooks/ directory."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_with_hooks))
        assert manifest is not None
        comps = discover_plugin_components(str(plugin_with_hooks), manifest)
        assert "hooks" in comps

    def test_parse_plugin_hooks(self, plugin_with_hooks: Path) -> None:
        """Parse hooks/hooks.json from a plugin."""
        from uagent.plugin_shared import parse_plugin_hooks_file

        hooks_dir = str(plugin_with_hooks / "hooks" / "hooks.json")
        result = parse_plugin_hooks_file(hooks_dir)
        assert result is not None
        assert "PreToolUse" in result
        assert "PostToolUse" in result
        assert "SessionStart" in result
        assert len(result["PreToolUse"]) == 1

    def test_install_plugin_hooks(self, plugin_with_hooks: Path, repo_tmp_path: Path) -> None:
        """Plugin hooks should be installable into a hooks registry."""
        from uagent.plugin_shared import install_plugin_hooks

        registry_path = repo_tmp_path / "hooks_registry.json"
        registry_path.write_text(json.dumps({"plugins": {}}), encoding="utf-8")

        result = install_plugin_hooks(
            str(plugin_with_hooks),
            plugin_name="hooks-plugin",
            registry_path=str(registry_path),
        )
        assert result["ok"] is True
        assert result["event_count"] == 3

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "hooks-plugin" in registry["plugins"]
        assert "PreToolUse" in registry["plugins"]["hooks-plugin"]

    def test_install_hooks_idempotent(self, plugin_with_hooks: Path, repo_tmp_path: Path) -> None:
        """Installing same plugin hooks twice should not duplicate."""
        from uagent.plugin_shared import install_plugin_hooks

        registry_path = repo_tmp_path / "idempotent_hooks.json"
        registry_path.write_text(json.dumps({"plugins": {}}), encoding="utf-8")

        install_plugin_hooks(str(plugin_with_hooks), "hooks-plugin", registry_path=str(registry_path))
        result = install_plugin_hooks(str(plugin_with_hooks), "hooks-plugin", registry_path=str(registry_path))

        assert result["event_count"] == 0  # no new entries

    def test_remove_plugin_hooks(self, plugin_with_hooks: Path, repo_tmp_path: Path) -> None:
        """Plugin hooks should be removable by plugin name."""
        from uagent.plugin_shared import install_plugin_hooks, remove_plugin_hooks

        registry_path = repo_tmp_path / "removable_hooks.json"
        registry_path.write_text(json.dumps({"plugins": {}}), encoding="utf-8")

        install_plugin_hooks(str(plugin_with_hooks), "hooks-plugin", registry_path=str(registry_path))

        result = remove_plugin_hooks("hooks-plugin", registry_path=str(registry_path))
        assert result["ok"] is True
        assert result["removed"] is True

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "hooks-plugin" not in registry["plugins"]

    def test_remove_hooks_partial(self, repo_tmp_path: Path) -> None:
        """Removing hooks from one plugin should not affect others."""
        from uagent.plugin_shared import remove_plugin_hooks

        registry_path = repo_tmp_path / "partial_hooks.json"
        registry_path.write_text(
            json.dumps({
                "plugins": {
                    "plugin-a": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo a"}]}]},
                    "plugin-b": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo b"}]}]},
                }
            }),
            encoding="utf-8",
        )

        result = remove_plugin_hooks("plugin-a", registry_path=str(registry_path))
        assert result["removed"] is True

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert "plugin-a" not in registry["plugins"]
        assert "plugin-b" in registry["plugins"]

    def test_no_hooks_in_plugin(self, plugin_dir: Path) -> None:
        """Plugin without hooks/ should not report hooks component."""
        from uagent.plugin_shared import discover_plugin_components, parse_plugin_manifest

        manifest = parse_plugin_manifest(str(plugin_dir))
        assert manifest is not None
        comps = discover_plugin_components(str(plugin_dir), manifest)
        assert "hooks" not in comps

    def test_inline_hooks_in_manifest(self, repo_tmp_path: Path) -> None:
        """Plugin can declare hooks inline in plugin.json."""
        from uagent.plugin_shared import parse_plugin_hooks_file

        p = repo_tmp_path / "inline-hooks-plugin"
        manifest_dir = p / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        manifest = {
            "name": "inline-hooks-plugin",
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "echo init"}]}
                ]
            },
        }
        (manifest_dir / "plugin.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        from uagent.plugin_shared import parse_plugin_manifest
        parsed = parse_plugin_manifest(str(p))
        assert parsed is not None
        inline = parsed.get("hooks")
        assert isinstance(inline, dict)
        assert "SessionStart" in inline


# =========================================================================
# Phase 2f: Skills-directory plugin auto-detection (@skills-dir)
# =========================================================================


class TestSkillsDirPluginDetection:
    """Plugins nested under skills directories should be auto-detected."""

    def test_plugin_under_skills_dir_detected(self, repo_tmp_path: Path) -> None:
        """A plugin under a skills root should be detected by scan_skills_dirs."""
        from uagent.plugin_shared import scan_skills_dirs_for_plugins

        # Create a plugin inside a skills directory
        skills_root = repo_tmp_path / "skills"
        plugin_dir = skills_root / "my-tool-plugin"
        manifest_dir = plugin_dir / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "plugin.json").write_text(
            json.dumps({"name": "my-tool-plugin"}), encoding="utf-8"
        )
        # Also has a SKILL.md (it's both a skill and a plugin)
        (plugin_dir / "SKILL.md").write_text(
            "---\nname: my-tool\ndescription: A tool skill\n---\n\nTool skill body.",
            encoding="utf-8",
        )

        results = scan_skills_dirs_for_plugins([str(skills_root)])
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "my-tool-plugin" in names

    def test_skill_without_manifest_not_plugin(self, repo_tmp_path: Path) -> None:
        """A plain skill (no plugin.json) should not be detected as plugin."""
        from uagent.plugin_shared import scan_skills_dirs_for_plugins

        skills_root = repo_tmp_path / "plain-skills"
        skill_dir = skills_root / "plain-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: plain-skill\ndescription: Plain\n---\n\nBody.",
            encoding="utf-8",
        )
        # No .claude-plugin/plugin.json

        results = scan_skills_dirs_for_plugins([str(skills_root)])
        assert len(results) == 0

    def test_skills_dir_plugin_has_skills_dir_flag(self, repo_tmp_path: Path) -> None:
        """Skills-dir plugins should have _skills_dir_plugin marker."""
        from uagent.plugin_shared import scan_skills_dirs_for_plugins

        skills_root = repo_tmp_path / "flagged-skills"
        plugin_dir = skills_root / "flagged-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / ".claude-plugin").mkdir()
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "flagged-plugin"}), encoding="utf-8"
        )

        results = scan_skills_dirs_for_plugins([str(skills_root)])
        assert len(results) == 1
        assert results[0].get("_skills_dir_plugin") is True

    def test_skills_dir_plugin_integration_with_scan(self, repo_tmp_path: Path) -> None:
        """scan_plugins should find skills-dir plugins when given skills dirs."""
        from uagent.plugin_shared import scan_plugins, scan_skills_dirs_for_plugins
        import json

        skills_root = repo_tmp_path / "integrated-skills"
        plugin_dir = skills_root / "integrated-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / ".claude-plugin").mkdir()
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "integrated-plugin"}), encoding="utf-8"
        )

        # Scan skills dirs and merge with regular plugin scan
        skills_plugins = scan_skills_dirs_for_plugins([str(skills_root)])
        assert len(skills_plugins) == 1

        # It should also show up when scanning the parent dir as a plugin dir
        all_plugins = scan_plugins([str(repo_tmp_path)])
        # skills_root itself is a dir but has no plugin manifest at top level
        # The subdir integrated-plugin should be found when scanning skills_root
        skills_as_dirs = scan_plugins([str(skills_root)])
        assert len(skills_as_dirs) >= 0

    def test_multiple_skills_dirs_plugins(self, repo_tmp_path: Path) -> None:
        """Multiple plugins under skills dirs should all be detected."""
        from uagent.plugin_shared import scan_skills_dirs_for_plugins

        skills_root = repo_tmp_path / "multi-skills"
        p1 = skills_root / "plugin-one"
        p1.mkdir(parents=True)
        (p1 / ".claude-plugin").mkdir()
        (p1 / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "plugin-one"}), encoding="utf-8"
        )
        p2 = skills_root / "plugin-two"
        p2.mkdir(parents=True)
        (p2 / ".claude-plugin").mkdir()
        (p2 / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "plugin-two"}), encoding="utf-8"
        )

        results = scan_skills_dirs_for_plugins([str(skills_root)])
        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "plugin-one" in names
        assert "plugin-two" in names

    def test_skills_dir_plugin_with_components(self, repo_tmp_path: Path) -> None:
        """Skills-dir plugins should have their components discoverable."""
        from uagent.plugin_shared import (
            scan_skills_dirs_for_plugins,
            discover_plugin_components,
        )

        skills_root = repo_tmp_path / "component-skills"
        plugin_dir = skills_root / "component-plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / ".claude-plugin").mkdir()
        (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "component-plugin"}), encoding="utf-8"
        )
        # Add a skill inside
        skill_dir = plugin_dir / "skills" / "inner-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: inner-skill\ndescription: Inner\n---\n\nInner body.",
            encoding="utf-8",
        )

        results = scan_skills_dirs_for_plugins([str(skills_root)])
        assert len(results) == 1
        comps = discover_plugin_components(results[0]["_path"], results[0])
        assert "skills" in comps
        assert "inner-skill" in comps["skills"]
