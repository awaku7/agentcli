"""Tests for plugin marketplace support."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def marketplace_dir(repo_tmp_path: Path) -> Path:
    """Create a marketplace directory with marketplace.json."""
    p = repo_tmp_path / "my-marketplace"
    (p / ".claude-plugin").mkdir(parents=True)

    # Create a plugin to distribute
    plugin_dir = p / "plugins" / "test-plugin"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "test-plugin", "version": "1.0.0", "description": "A test plugin"}),
        encoding="utf-8",
    )

    # Marketplace catalog
    marketplace = {
        "name": "my-marketplace",
        "owner": {"name": "Test Owner"},
        "plugins": [
            {
                "name": "test-plugin",
                "source": "./plugins/test-plugin",
                "description": "A test plugin from marketplace",
            }
        ],
    }
    (p / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(marketplace, indent=2), encoding="utf-8"
    )
    return p


class TestMarketplaceParse:
    """Tests for parsing marketplace.json."""

    def test_parse_marketplace(self, marketplace_dir: Path) -> None:
        """marketplace.json should be parseable."""
        from uagent.plugin_shared import parse_marketplace

        mp = parse_marketplace(str(marketplace_dir / ".claude-plugin" / "marketplace.json"))
        assert mp is not None
        assert mp["name"] == "my-marketplace"
        assert len(mp["plugins"]) == 1

    def test_parse_invalid_path(self, repo_tmp_path: Path) -> None:
        """Invalid path should return None."""
        from uagent.plugin_shared import parse_marketplace

        mp = parse_marketplace(str(repo_tmp_path / "nonexistent.json"))
        assert mp is None

    def test_marketplace_plugins_list(self, marketplace_dir: Path) -> None:
        """Should return list of available plugins."""
        from uagent.plugin_shared import parse_marketplace

        mp = parse_marketplace(str(marketplace_dir / ".claude-plugin" / "marketplace.json"))
        plugins = mp["plugins"]
        assert plugins[0]["name"] == "test-plugin"
        assert "source" in plugins[0]


class TestMarketplaceInstall:
    """Tests for installing from marketplace."""

    def test_install_from_marketplace(self, marketplace_dir: Path, repo_tmp_path: Path) -> None:
        """Plugin should be installable from marketplace source."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        dest = repo_tmp_path / "mp-installed"
        dest.mkdir(parents=True)

        result = run_tool({
            "action": "install",
            "source": str(marketplace_dir / "plugins" / "test-plugin"),
            "name": "marketplace-plugin",
            "_test_install_root": str(dest),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert (dest / "marketplace-plugin").exists()
        assert (dest / "marketplace-plugin" / ".claude-plugin" / "plugin.json").exists()

    def test_install_from_marketplace_name_inferred(self, marketplace_dir: Path, repo_tmp_path: Path) -> None:
        """Plugin name should be inferred from marketplace source."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        dest = repo_tmp_path / "mp-inferred"
        dest.mkdir(parents=True)

        result = run_tool({
            "action": "install",
            "source": str(marketplace_dir / "plugins" / "test-plugin"),
            "_test_install_root": str(dest),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        # Name should be inferred from source path (test-plugin)
        assert "test-plugin" in parsed.get("name", "")


class TestMarketplaceManager:
    """Tests for marketplace registry management."""

    def test_add_marketplace(self, repo_tmp_path: Path) -> None:
        """Marketplace should be storable in registry."""
        from uagent.plugin_shared import add_marketplace, list_marketplaces

        registry_path = repo_tmp_path / "mp_registry.json"
        registry_path.write_text(json.dumps({"marketplaces": []}), encoding="utf-8")

        add_marketplace("my-marketplace", "https://example.com/mp", registry_path=str(registry_path))

        mps = list_marketplaces(registry_path=str(registry_path))
        assert len(mps) == 1
        assert mps[0]["name"] == "my-marketplace"
        assert mps[0]["url"] == "https://example.com/mp"

    def test_remove_marketplace(self, repo_tmp_path: Path) -> None:
        """Marketplace should be removable from registry."""
        from uagent.plugin_shared import add_marketplace, remove_marketplace, list_marketplaces

        registry_path = repo_tmp_path / "mp_remove.json"
        registry_path.write_text(json.dumps({"marketplaces": []}), encoding="utf-8")

        add_marketplace("mp1", "https://example.com/1", registry_path=str(registry_path))
        add_marketplace("mp2", "https://example.com/2", registry_path=str(registry_path))

        remove_marketplace("mp1", registry_path=str(registry_path))
        mps = list_marketplaces(registry_path=str(registry_path))
        assert len(mps) == 1
        assert mps[0]["name"] == "mp2"

    def test_list_marketplaces_empty(self, repo_tmp_path: Path) -> None:
        """Empty registry should return empty list."""
        from uagent.plugin_shared import list_marketplaces

        registry_path = repo_tmp_path / "mp_empty.json"
        registry_path.write_text(json.dumps({"marketplaces": []}), encoding="utf-8")

        mps = list_marketplaces(registry_path=str(registry_path))
        assert mps == []


class TestMarketplaceInstallFrom:
    """Tests for installing plugins from marketplace."""

    def test_resolve_marketplace_plugin(self, marketplace_dir: Path, repo_tmp_path: Path) -> None:
        """Should resolve plugin source from marketplace name."""
        from uagent.plugin_shared import resolve_marketplace_plugin

        source = resolve_marketplace_plugin(
            "test-plugin",
            "my-marketplace",
            marketplace_dir=str(marketplace_dir),
        )
        assert source is not None
        assert "plugins" in source and "test-plugin" in source

    def test_resolve_unknown_plugin(self, marketplace_dir: Path) -> None:
        """Unknown plugin should return None."""
        from uagent.plugin_shared import resolve_marketplace_plugin

        source = resolve_marketplace_plugin(
            "nonexistent",
            "my-marketplace",
            marketplace_dir=str(marketplace_dir),
        )
        assert source is None

    def test_resolve_unknown_marketplace(self, repo_tmp_path: Path) -> None:
        """Unknown marketplace should return None."""
        from uagent.plugin_shared import resolve_marketplace_plugin

        source = resolve_marketplace_plugin(
            "test-plugin",
            "unknown-marketplace",
        )
        assert source is None

    def test_install_from_marketplace_syntax(self, marketplace_dir: Path, repo_tmp_path: Path) -> None:
        """`name@marketplace` syntax should install from marketplace."""
        from uagent.tools.plugin_manage_tool import run_tool
        import json

        dest = repo_tmp_path / "mp-syntax-installed"
        dest.mkdir(parents=True)

        result = run_tool({
            "action": "install",
            "source": "test-plugin@my-marketplace",
            "_test_install_root": str(dest),
            "_test_marketplace_dir": str(marketplace_dir),
        })
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert (dest / "test-plugin").exists()
        assert (dest / "test-plugin" / ".claude-plugin" / "plugin.json").exists()


class TestPluginDependencies:
    """Tests for plugin dependency resolution."""

    def test_parse_dependencies(self, repo_tmp_path: Path) -> None:
        """Dependencies field in plugin.json should be parseable."""
        from uagent.plugin_shared import parse_plugin_dependencies

        p = repo_tmp_path / "dep-plugin"
        (p / ".claude-plugin").mkdir(parents=True)
        (p / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({
                "name": "dep-plugin",
                "dependencies": [
                    "base-lib",
                    {"name": "secrets-vault", "version": "~2.1.0"},
                ],
            }),
            encoding="utf-8",
        )
        from uagent.plugin_shared import parse_plugin_manifest
        manifest = parse_plugin_manifest(str(p))
        assert manifest is not None
        deps = parse_plugin_dependencies(manifest)
        assert len(deps) == 2
        assert deps[0]["name"] == "base-lib"
        assert deps[1]["name"] == "secrets-vault"
        assert deps[1].get("version") == "~2.1.0"

    def test_dependencies_empty(self) -> None:
        """No dependencies should return empty list."""
        from uagent.plugin_shared import parse_plugin_dependencies

        deps = parse_plugin_dependencies({})
        assert deps == []

    def test_dependencies_not_present(self) -> None:
        """Missing dependencies field should return empty list."""
        from uagent.plugin_shared import parse_plugin_dependencies

        deps = parse_plugin_dependencies({"name": "test"})
        assert deps == []

    def test_parse_dependency_string_form(self, repo_tmp_path: Path) -> None:
        """Dependencies can be simple strings."""
        from uagent.plugin_shared import parse_plugin_dependencies

        manifest = {
            "dependencies": ["helper-lib", "another-lib"],
        }
        deps = parse_plugin_dependencies(manifest)
        assert len(deps) == 2
        assert deps[0]["name"] == "helper-lib"

    def test_resolve_dependencies_chain(self) -> None:
        """Dependency resolution should resolve in order."""
        from uagent.plugin_shared import resolve_dependencies

        # Simple chain: A depends on B, B depends on C
        registry = {
            "plugin-a": {"dependencies": [{"name": "plugin-b"}]},
            "plugin-b": {"dependencies": [{"name": "plugin-c"}]},
            "plugin-c": {"dependencies": []},
        }
        resolved = resolve_dependencies("plugin-a", registry)
        # plugin-c should come before plugin-b
        assert "plugin-c" in resolved
        assert "plugin-b" in resolved
        c_idx = resolved.index("plugin-c")
        b_idx = resolved.index("plugin-b")
        assert c_idx < b_idx  # c before b (dependency order)
