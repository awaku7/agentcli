from __future__ import annotations

from pathlib import Path

import pytest


def test_handle_cmd_ls_globstar_recursive_lists_nested_paths(
    repo_tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from uagent.util_tools import _handle_cmd_ls

    (repo_tmp_path / "root.org").write_text("x", encoding="utf-8")
    nested = repo_tmp_path / "dir" / "subdir"
    nested.mkdir(parents=True)
    (nested / "child.org1").write_text("y", encoding="utf-8")
    (nested / "ignore.txt").write_text("z", encoding="utf-8")

    monkeypatch.chdir(repo_tmp_path)

    ok = _handle_cmd_ls("**/*.org*", tr=lambda s: s)
    out = capsys.readouterr().out

    assert ok is True
    assert "root.org" in out
    assert "child.org1" in out
    assert "ignore.txt" not in out
