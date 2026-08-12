import importlib.util
import json
import subprocess

import pytest

from uagent.tools import coverage_report_tool, git_review_tool, security_scan_tool


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def test_git_review_uses_real_repository(tmp_path, monkeypatch):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "ci@example.test")
    _git(tmp_path, "config", "user.name", "CI")
    tracked = tmp_path / "src.py"
    tracked.write_text("print('one')\n", encoding="utf-8")
    _git(tmp_path, "add", "src.py")
    _git(tmp_path, "commit", "-m", "initial")
    tracked.write_text("print('two')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = json.loads(git_review_tool.run_tool({"scan_secrets": False}))

    assert result["ok"] is True
    assert result["file_count"] == 1
    assert result["files"][0]["path"] == "src.py"
    assert result["additions"] == 1
    assert result["deletions"] == 1


def test_security_scan_uses_real_repository_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "settings.env").write_text(
        "ACCESS_TOKEN=abcdefghijklmnop\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("safe\n", encoding="utf-8")

    result = json.loads(security_scan_tool.run_tool({"root": "."}))

    assert result["ok"] is True
    assert any(
        item["path"].endswith("settings.env") for item in result["secret_findings"]
    )
    assert "abcdefghijklmnop" not in json.dumps(result)


@pytest.mark.skipif(
    importlib.util.find_spec("coverage") is None, reason="coverage is not installed"
)
def test_coverage_report_runs_real_python_test(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test_smoke.py").write_text(
        "def test_smoke():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )

    result = json.loads(
        coverage_report_tool.run_tool(
            {"language": "python", "test_target": "test_smoke.py", "timeout": 60}
        )
    )

    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "coverage" in result
    assert result["coverage"]["percent_covered"] >= 0
