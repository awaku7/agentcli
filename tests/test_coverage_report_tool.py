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


def test_coverage_parsers_normalize_language_reports(tmp_path):
    ts = tmp_path / "coverage-final.json"
    ts.write_text(
        '{"a.ts":{"lines":{"covered":3,"total":4},"statements":{"covered":3,"total":4},"functions":{"covered":1,"total":2},"branches":{"covered":2,"total":4}}}',
        encoding="utf-8",
    )
    rust = tmp_path / "rust.json"
    rust.write_text(
        '{"data":[{"totals":{"lines":{"percent":75.0},"functions":{"percent":50.0}}}]}',
        encoding="utf-8",
    )
    go = tmp_path / "cover.out"
    go.write_text("mode: set\na.go:1.1,2.2 2 1\na.go:3.1,4.2 3 0\n", encoding="utf-8")

    assert coverage_report_tool._parse_typescript(ts)["lines_percent"] == 75.0
    assert coverage_report_tool._parse_rust(rust)["lines_percent"] == 75.0
    assert coverage_report_tool._parse_go(go)["statements_percent"] == 40.0
