import json

from uagent.tools import security_scan_tool


def test_security_scan_detects_secret_without_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.env").write_text(
        "ACCESS_TOKEN=abcdefghijklmnop\n", encoding="utf-8"
    )
    result = json.loads(security_scan_tool.run_tool({"root": str(tmp_path)}))
    assert result["ok"] is True
    assert result["secret_findings"]
    assert "abcdefghijklmnop" not in json.dumps(result)


def test_security_scan_skips_git_and_hidden_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".hidden").write_text(
        "ACCESS_TOKEN=abcdefghijklmnop\n", encoding="utf-8"
    )
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("ACCESS_TOKEN=abcdefghijklmnop\n", encoding="utf-8")
    result = json.loads(security_scan_tool.run_tool({"root": str(tmp_path)}))
    assert result["secret_findings"] == []


def test_security_scan_rejects_invalid_root(tmp_path):
    result = json.loads(
        security_scan_tool.run_tool({"root": str(tmp_path / "missing")})
    )
    assert result["ok"] is False
