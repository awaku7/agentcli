from __future__ import annotations

from pathlib import Path

import pytest

from uagent.tools import list_dir_tool


def test_list_dir_tool_uses_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta.txt").write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    out = list_dir_tool.run_tool({})

    assert "Path: " in out
    assert "[DIR] alpha/" in out
    assert "[FILE] beta.txt" in out


def test_list_dir_tool_hides_hidden_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".hidden.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    out = list_dir_tool.run_tool({})

    assert "visible.txt" in out
    assert ".hidden.txt" not in out


def test_list_dir_tool_includes_hidden_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".hidden.txt").write_text("secret", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    out = list_dir_tool.run_tool({"show_hidden": True})

    assert ".hidden.txt" in out


def test_list_dir_tool_accepts_path_alias(tmp_path: Path) -> None:
    target = tmp_path / "nested"
    target.mkdir()
    (target / "item.txt").write_text("x", encoding="utf-8")

    out = list_dir_tool.run_tool({"path": str(target)})

    assert "item.txt" in out


def test_list_dir_tool_accepts_root_path_alias(tmp_path: Path) -> None:
    target = tmp_path / "nested"
    target.mkdir()
    (target / "item.txt").write_text("x", encoding="utf-8")

    out = list_dir_tool.run_tool({"root_path": str(target)})

    assert "item.txt" in out


def test_list_dir_tool_missing_dir() -> None:
    out = list_dir_tool.run_tool({"path": "does_not_exist_12345"})

    assert "does not exist" in out.lower()
