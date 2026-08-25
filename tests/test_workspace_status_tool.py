from __future__ import annotations

import json
import subprocess

import pytest

from uagent.tools import workspace_status_tool as tool


def test_run_reports_git_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(tool.subprocess, "run", missing_git)
    assert tool._run(["git", "status"], ".") == (127, "", "git_unavailable")
    assert tool._git_status(".") == {
        "is_repository": False,
        "reason": "git_unavailable",
    }


def test_git_status_reports_untracked_and_dirty(tmp_path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "new.txt").write_text("new", encoding="utf-8")

    result = tool._git_status(str(tmp_path))

    assert result["is_repository"] is True
    assert result["has_commits"] is False
    assert result["dirty"] is True
    assert result["untracked_count"] == 1
    assert result["changed_file_count"] == 1
    assert result["tracking"] is False
    assert result["changes_truncated"] is False


def test_parse_git_status_branch_and_ahead_behind() -> None:
    result = tool._parse_git_status(
        "\n".join(
            [
                "# branch.oid abcdef1234567890",
                "# branch.head main",
                "# branch.upstream origin/main",
                "# branch.ab +3 -2",
                "1 M. N... 100644 100644 100644 abc abc file.txt",
                "? new.txt",
            ]
        )
    )

    assert result["branch"] == "main"
    assert result["head"] == "abcdef1"
    assert result["ahead"] == 3
    assert result["behind"] == 2
    assert result["staged_count"] == 1
    assert result["untracked_count"] == 1
    assert result["dirty"] is True


def test_run_tool_uses_git_root_for_markers(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    subdir = root / "src"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    monkeypatch.setattr(
        tool,
        "_git_status",
        lambda cwd: {"is_repository": True, "root": str(root)},
    )

    payload = json.loads(tool.run_tool({}))
    assert payload["project_markers"]["pyproject.toml"] is True
