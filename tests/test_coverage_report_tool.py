import json

from uagent.tools import coverage_report_tool


def test_coverage_dry_run_detects_python(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]", encoding="utf-8")
    result = json.loads(
        coverage_report_tool.run_tool({"language": "auto", "dry_run": True})
    )
    assert result["ok"] is True
    assert result["adapter"] == "python"
    assert "coverage" in result["command"]


def test_coverage_rejects_unsafe_target():
    result = json.loads(
        coverage_report_tool.run_tool(
            {"language": "python", "test_target": "../tests", "dry_run": True}
        )
    )
    assert result["ok"] is False


def test_coverage_rejects_unknown_language():
    result = json.loads(
        coverage_report_tool.run_tool({"language": "ruby", "dry_run": True})
    )
    assert result["ok"] is False


def test_coverage_auto_installs_python_dependencies(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    installed = []
    monkeypatch.setattr(
        coverage_report_tool,
        "_auto_install",
        lambda package, module: installed.append((package, module)) or True,
    )
    monkeypatch.setattr(
        coverage_report_tool, "_run", lambda command, timeout: (0, "", "")
    )

    result = json.loads(
        coverage_report_tool.run_tool(
            {"language": "python", "auto_install": True, "timeout": 10}
        )
    )

    assert result["ok"] is True
    assert installed == [("coverage", "coverage"), ("pytest", "pytest")]


def test_coverage_auto_installs_typescript_and_rust_tools(monkeypatch):
    commands = []

    def fake_run(command, timeout):
        commands.append(command)
        if command[:4] == ["npx", "--no-install", "c8", "--version"]:
            return 1, "", "missing c8"
        if command[:3] == ["cargo", "llvm-cov", "--version"]:
            return 1, "", "missing llvm-cov"
        return 0, "", ""

    monkeypatch.setattr(coverage_report_tool, "_run", fake_run)

    coverage_report_tool._ensure_dependencies("typescript", True, 10)
    coverage_report_tool._ensure_dependencies("rust", True, 10)

    assert ["npm", "install", "--no-save", "c8"] in commands
    assert ["cargo", "install", "cargo-llvm-cov"] in commands
