from __future__ import annotations

import json
from pathlib import Path

import pytest


def _run_delete_file(args: dict) -> dict:
    from uagent.tools.delete_file_tool import run_tool

    out = run_tool(args)
    assert isinstance(out, str)
    return json.loads(out)


def test_delete_file_glob_dry_run_lists_matches(repo_tmp_path: Path) -> None:
    # Arrange
    (repo_tmp_path / "a.org").write_text("x", encoding="utf-8")
    (repo_tmp_path / "b.org1").write_text("y", encoding="utf-8")
    (repo_tmp_path / "c.txt").write_text("z", encoding="utf-8")

    # Act (glob meta present -> glob mode; dry_run default True)
    res = _run_delete_file(
        {
            "filename": str(repo_tmp_path / "*.org*"),
            "missing_ok": False,
        }
    )

    # Assert
    assert res["ok"] is True
    assert res.get("dry_run") is True
    assert res["count"] == 2
    matches = [Path(p).name for p in res["matches"]]
    assert sorted(matches) == ["a.org", "b.org1"]


def test_delete_file_glob_missing_ok_when_no_matches(repo_tmp_path: Path) -> None:
    # Act
    res = _run_delete_file(
        {
            "filename": str(repo_tmp_path / "*.org*"),
            "missing_ok": True,
        }
    )

    # Assert
    assert res["ok"] is True
    assert res["deleted"] is False
    assert res["count"] == 0
    assert res["matches"] == []


def test_delete_file_single_path_deletes_file(
    monkeypatch: pytest.MonkeyPatch, repo_tmp_path: Path
) -> None:
    # Arrange
    target = repo_tmp_path / "x.txt"
    target.write_text("hi", encoding="utf-8")

    # Always confirm yes, without prompting interactive human_ask.
    monkeypatch.setattr(
        "uagent.tools.delete_file_tool._human_confirm",
        lambda _msg: True,
    )

    # Act
    res = _run_delete_file(
        {
            "filename": str(target),
            "missing_ok": False,
        }
    )

    # Assert
    assert res["ok"] is True
    assert res["deleted"] is True
    assert Path(res["path"]).name == "x.txt"
    assert not target.exists()
