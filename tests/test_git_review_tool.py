import json

from uagent.tools import git_review_tool


def test_git_review_tool_has_valid_spec():
    spec = git_review_tool.TOOL_SPEC["function"]
    assert spec["name"] == "git_review"
    assert spec["parameters"]["type"] == "object"


def test_secret_scan_returns_kind_without_secret_value(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("OPENAI_API_KEY=abcdefghijklmnop\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        git_review_tool,
        "_changed_files",
        lambda staged, include: [{"path": ".env", "status": "??"}],
    )
    monkeypatch.setattr(git_review_tool, "_run_git", lambda args: (True, "", ""))

    result = json.loads(git_review_tool.run_tool({"scan_secrets": True}))
    assert result["ok"] is True
    assert result["secret_findings"][0]["kind"] == "provider_key"
    assert "abcdefghijklmnop" not in json.dumps(result)


def test_tracked_modified_file_is_scanned(monkeypatch, tmp_path):
    p = tmp_path / "config.py"
    p.write_text("access_token = 'abcdefghijklmnop'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        git_review_tool,
        "_changed_files",
        lambda staged, include: [{"path": "config.py", "status": " M"}],
    )
    monkeypatch.setattr(git_review_tool, "_run_git", lambda args: (True, "", ""))
    result = json.loads(git_review_tool.run_tool({"scan_secrets": True}))
    assert result["secret_findings"]


def test_test_candidates_find_conventional_pytest(tmp_path, monkeypatch):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_widget.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = git_review_tool._test_candidates(
        [{"path": "src/widget.py", "status": " M"}]
    )
    assert result == [{"source": "src/widget.py", "tests": ["tests/test_widget.py"]}]


def test_invalid_max_files_is_structured_error():
    result = json.loads(git_review_tool.run_tool({"max_files": 0}))
    assert result["ok"] is False
    assert "max_files" in result["error"]
