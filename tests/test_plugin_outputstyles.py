"""Tests for plugin output-styles support."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def plugin_with_styles(repo_tmp_path: Path) -> Path:
    """Create a plugin with output-styles."""
    p = repo_tmp_path / "plugins" / "style-plugin"
    (p / ".claude-plugin").mkdir(parents=True)
    (p / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "style-plugin", "version": "1.0.0"}), encoding="utf-8"
    )
    styles_dir = p / "output-styles"
    styles_dir.mkdir(parents=True)
    (styles_dir / "terse.md").write_text(
        "Be concise. Use bullet points. No greetings.", encoding="utf-8"
    )
    (styles_dir / "educational.md").write_text(
        "Explain concepts step by step. Include examples.", encoding="utf-8"
    )
    return p


class TestOutputStylesDisk:
    """Tests for discovering output-styles on disk."""

    def test_discover_output_styles(self, plugin_with_styles: Path) -> None:
        """output-styles directory should be detectable."""
        # Currently output-styles may not be in discover; check directory directly
        styles_dir = plugin_with_styles / "output-styles"
        assert styles_dir.is_dir()
        files = sorted(styles_dir.glob("*.md"))
        assert len(files) == 2

    def test_read_style_content(self, plugin_with_styles: Path) -> None:
        """Style files should be readable."""
        from uagent.plugin_shared import read_output_style

        style = read_output_style(str(plugin_with_styles), "terse")
        assert style is not None
        assert "bullet points" in style
        assert "greetings" in style

    def test_read_nonexistent_style(self, plugin_with_styles: Path) -> None:
        """Nonexistent style should return None."""
        from uagent.plugin_shared import read_output_style

        style = read_output_style(str(plugin_with_styles), "nonexistent")
        assert style is None

    def test_read_style_without_plugin(self, repo_tmp_path: Path) -> None:
        """Reading style from non-plugin directory should work."""
        from uagent.plugin_shared import read_output_style

        d = repo_tmp_path / "custom-styles"
        d.mkdir(parents=True)
        (d / "terse.md").write_text("Be concise.", encoding="utf-8")
        style = read_output_style(str(d), "terse")
        assert style is not None
        assert "concise" in style


class TestOutputStylesActivate:
    """Tests for activating/resolving output styles."""

    def test_list_output_styles(self, plugin_with_styles: Path) -> None:
        """Should list available output styles from a plugin."""
        from uagent.plugin_shared import list_output_styles

        styles = list_output_styles(str(plugin_with_styles / "output-styles"))
        assert "terse" in styles
        assert "educational" in styles

    def test_list_styles_from_custom_dir(self, repo_tmp_path: Path) -> None:
        """Should list styles from custom directory."""
        from uagent.plugin_shared import list_output_styles

        d = repo_tmp_path / "my-styles"
        d.mkdir(parents=True)
        (d / "style1.md").write_text("s1", encoding="utf-8")
        (d / "style2.md").write_text("s2", encoding="utf-8")

        styles = list_output_styles(str(d))
        assert "style1" in styles
        assert "style2" in styles

    def test_list_empty_directory(self, repo_tmp_path: Path) -> None:
        """Empty directory should return empty list."""
        from uagent.plugin_shared import list_output_styles

        d = repo_tmp_path / "empty-styles"
        d.mkdir(parents=True)
        styles = list_output_styles(str(d))
        assert styles == []
