"""Run supported project coverage commands with a normalized result."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .._pip_auto import auto_install as _auto_install
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)
BUSY_LABEL = True
STATUS_LABEL = "tool:coverage_report"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "devel",
    "type": "function",
    "function": {
        "name": "coverage_report",
        "description": _(
            "tool.description",
            default="Run project coverage using a detected language tool and return execution and coverage data when available.",
        ),
        "x_search_terms": ["coverage", "test coverage", "カバレッジ", "テスト網羅率"],
        "x_search_terms_en": [
            "coverage",
            "test coverage",
            "line coverage",
            "branch coverage",
            "lcov",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "python",
                        "typescript",
                        "rust",
                        "go",
                        "java",
                        "kotlin",
                        "dotnet",
                        "cpp",
                        "ruby",
                        "php",
                        "swift",
                    ],
                    "description": _(
                        "param.language.description", default="Coverage adapter to use."
                    ),
                    "default": "auto",
                },
                "test_target": {
                    "type": "string",
                    "description": _(
                        "param.test_target.description",
                        default="Optional safe test target, such as a test directory.",
                    ),
                    "default": "",
                },
                "timeout": {
                    "type": "integer",
                    "description": _(
                        "param.timeout.description",
                        default="Maximum execution time in seconds.",
                    ),
                    "default": 300,
                    "minimum": 1,
                    "maximum": 3600,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": _(
                        "param.dry_run.description",
                        default="Only report the detected adapter and command without running tests.",
                    ),
                    "default": False,
                },
                "auto_install": {
                    "type": "boolean",
                    "description": _(
                        "param.auto_install.description",
                        default="Automatically install missing Python coverage dependencies with pip.",
                    ),
                    "default": True,
                },
            },
        },
    },
}


def _detect_language(root: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if (root / "package.json").exists() or list(root.glob("**/*.ts")):
        return "typescript"
    if (root / "Cargo.toml").exists():
        return "rust"
    if (root / "go.mod").exists():
        return "go"
    if (root / "pom.xml").exists() or (root / "build.gradle").exists():
        return "java"
    if list(root.glob("**/*.kt")) or (root / "settings.gradle.kts").exists():
        return "kotlin"
    if list(root.glob("**/*.sln")) or list(root.glob("**/*.csproj")):
        return "dotnet"
    if (root / "CMakeLists.txt").exists() or list(root.glob("**/*.cpp")):
        return "cpp"
    if (root / "Gemfile").exists() or list(root.glob("**/*.rb")):
        return "ruby"
    if (
        (root / "composer.json").exists()
        or (root / "phpunit.xml").exists()
        or list(root.glob("**/*.php"))
    ):
        return "php"
    if (root / "Package.swift").exists() or list(root.glob("**/*.swift")):
        return "swift"
    if (
        (root / "pyproject.toml").exists()
        or (root / "pytest.ini").exists()
        or list(root.glob("**/*.py"))
    ):
        return "python"
    return "unknown"


def _adapter(language: str, target: str, output: Path) -> tuple[str, list[str], str]:
    if target and (Path(target).is_absolute() or ".." in Path(target).parts):
        raise ValueError("test_target must be a relative path without ..")
    if language == "python":
        return (
            "Python",
            [
                "python",
                "-m",
                "coverage",
                "run",
                "-m",
                "pytest",
                *([target] if target else []),
            ],
            "python -m coverage json",
        )
    if language == "typescript":
        return (
            "TypeScript/JavaScript",
            [
                "npx",
                "--no-install",
                "c8",
                "--reporter=json",
                "--reporter=text",
                "npm",
                "test",
            ],
            "npx --no-install c8 --reporter=json --reporter=text npm test",
        )
    if language == "rust":
        return (
            "Rust",
            ["cargo", "llvm-cov", "--json", "--output-path", str(output)],
            "cargo llvm-cov --json",
        )
    if language == "go":
        return (
            "Go",
            ["go", "test", "-coverprofile", str(output), "./..."],
            "go test -coverprofile",
        )
    if language in {"java", "kotlin"}:
        if Path("gradlew").is_file() or Path("gradlew.bat").is_file():
            return (
                "Java/Kotlin",
                ["gradle", "test", "jacocoTestReport"],
                "gradle test jacocoTestReport",
            )
        return (
            "Java/Kotlin",
            ["mvn", "test", "jacoco:report"],
            "mvn test jacoco:report",
        )
    if language == "dotnet":
        return (
            ".NET",
            ["dotnet", "test", "--collect:XPlat Code Coverage"],
            "dotnet test --collect:XPlat Code Coverage",
        )
    if language == "cpp":
        return (
            "C/C++",
            ["cmake", "--build", "build", "--target", "test"],
            "cmake --build build --target test",
        )
    if language == "ruby":
        return (
            "Ruby",
            ["bundle", "exec", "rake", "test"],
            "bundle exec rake test",
        )
    if language == "php":
        return (
            "PHP",
            ["vendor/bin/phpunit", "--coverage-clover", "coverage.xml"],
            "vendor/bin/phpunit --coverage-clover coverage.xml",
        )
    if language == "swift":
        return (
            "Swift",
            ["swift", "test", "--enable-code-coverage"],
            "swift test --enable-code-coverage",
        )
    raise ValueError("no supported coverage adapter was detected")


def _run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.update({"GIT_PAGER": "cat", "CI": "1"})
    try:
        p = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        return int(p.returncode), p.stdout[-20000:], p.stderr[-20000:]
    except FileNotFoundError:
        return 127, "", "required coverage command was not found"
    except subprocess.TimeoutExpired:
        return 124, "", "coverage command timed out"


def _ratio(covered: float, total: float) -> float:
    return round((covered / total) * 100, 2) if total else 100.0


def _parse_typescript(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    totals = {
        "lines": [0, 0],
        "statements": [0, 0],
        "functions": [0, 0],
        "branches": [0, 0],
    }
    for item in report.values():
        for key in totals:
            metrics = item.get(key, {}) if isinstance(item, dict) else {}
            totals[key][0] += int(metrics.get("covered", 0))
            totals[key][1] += int(metrics.get("total", 0))
    return {
        f"{key}_percent": _ratio(covered, total)
        for key, (covered, total) in totals.items()
    }


def _parse_rust(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    data = report.get("data", [])
    totals = data[0].get("totals", {}) if data else {}
    result = {}
    for key, value in totals.items():
        if isinstance(value, dict) and "percent" in value:
            result[f"{key}_percent"] = value["percent"]
    return result or None


def _parse_go(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    covered = total = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines[1:]:
        try:
            _, count = line.rsplit(" ", 1)
            _, statements, _ = line.rsplit(" ", 2)
            total += int(statements)
            covered += int(statements) if int(count) > 0 else 0
        except (ValueError, IndexError):
            continue
    return {"statements_percent": _ratio(covered, total)} if total else None


def _parse_xml_coverage(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    counters = {}
    for counter in root.iter("counter"):
        kind = (counter.get("type") or "").lower()
        covered = int(counter.get("covered", 0))
        missed = int(counter.get("missed", 0))
        if kind:
            counters[f"{kind}_percent"] = _ratio(covered, covered + missed)
    if counters:
        return counters
    for metrics in root.iter("metrics"):
        total = int(metrics.get("statements", 0))
        covered = int(metrics.get("coveredstatements", 0))
        if total:
            return {"statements_percent": _ratio(covered, total)}
    result = {}
    for key in ("line-rate", "branch-rate", "function-rate"):
        value = root.get(key)
        if value is not None:
            result[f"{key[:-5]}_percent"] = round(float(value) * 100, 2)
    return result or None


def _parse_lcov(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("LF:", "LH:")):
                key, value = line.split(":", 1)
                values[key] = values.get(key, 0) + int(value)
    except (OSError, ValueError):
        return None
    if "LF" not in values:
        return None
    return {"lines_percent": _ratio(values.get("LH", 0), values["LF"])}


def _parse_simplecov(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    covered = total = 0
    for item in report.get("files", {}).values():
        lines = item.get("coverage", []) if isinstance(item, dict) else []
        executable = [value for value in lines if value is not None]
        total += len(executable)
        covered += sum(value > 0 for value in executable)
    return {"lines_percent": _ratio(covered, total)} if total else None


def _sorted_files(pattern: str) -> list[Path]:
    return sorted(Path.cwd().glob(pattern))


def _first_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.is_file()), None)


def _ensure_dependencies(language: str, auto_install: bool, timeout: int) -> None:
    if language == "python":
        if not auto_install:
            return
        if not _auto_install("coverage", "coverage"):
            raise RuntimeError("coverage is required and could not be installed")
        if not _auto_install("pytest", "pytest"):
            raise RuntimeError("pytest is required and could not be installed")
        return
    if language == "typescript":
        code, _, _ = _run(["npx", "--no-install", "c8", "--version"], timeout)
        if code == 0 or not auto_install:
            return
        code, _, error = _run(["npm", "install", "--no-save", "c8"], timeout)
        if code != 0:
            raise RuntimeError(error or "c8 is required and could not be installed")
        return
    if language == "rust":
        code, _, _ = _run(["cargo", "llvm-cov", "--version"], timeout)
        if code == 0 or not auto_install:
            return
        code, _, error = _run(["cargo", "install", "cargo-llvm-cov"], timeout)
        if code != 0:
            raise RuntimeError(
                error or "cargo-llvm-cov is required and could not be installed"
            )


def run_tool(args: dict[str, Any]) -> str:
    try:
        requested = str(args.get("language", "auto") or "auto")
        if requested not in {
            "auto",
            "python",
            "typescript",
            "rust",
            "go",
            "java",
            "kotlin",
            "dotnet",
            "cpp",
            "ruby",
            "php",
            "swift",
        }:
            raise ValueError("unsupported language")
        timeout = int(args.get("timeout", 300))
        if not 1 <= timeout <= 3600:
            raise ValueError("timeout must be between 1 and 3600")
        language = _detect_language(Path.cwd(), requested)
        with tempfile.TemporaryDirectory(prefix="uagent-coverage-") as temp:
            output = Path(temp) / "coverage.json"
            label, command, display = _adapter(
                language, str(args.get("test_target", "") or ""), output
            )
            result: dict[str, Any] = {
                "ok": True,
                "language": label,
                "adapter": language,
                "command": display,
                "dry_run": bool(args.get("dry_run", False)),
            }
            if args.get("dry_run", False):
                result["available"] = shutil.which(command[0]) is not None
                return json.dumps(result, ensure_ascii=False)
            _ensure_dependencies(
                language, bool(args.get("auto_install", True)), timeout
            )
            code, stdout, stderr = _run(command, timeout)
            result.update(
                {
                    "ok": code == 0,
                    "returncode": code,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            if code == 0 and language == "python":
                json_code, _, json_err = _run(
                    ["python", "-m", "coverage", "json", "-o", str(output)], timeout
                )
                if json_code == 0 and output.is_file():
                    try:
                        report = json.loads(output.read_text(encoding="utf-8"))
                        result["coverage"] = report.get("totals", {})
                    except (OSError, json.JSONDecodeError) as exc:
                        result["coverage_error"] = str(exc)
                elif json_err:
                    result["coverage_error"] = json_err
            elif code == 0 and language == "typescript":
                coverage = _parse_typescript(
                    Path.cwd() / "coverage" / "coverage-final.json"
                )
                if coverage:
                    result["coverage"] = coverage
            elif code == 0 and language == "rust":
                coverage = _parse_rust(output)
                if coverage:
                    result["coverage"] = coverage
            elif code == 0 and language == "go":
                coverage = _parse_go(output)
                if coverage:
                    result["coverage"] = coverage
            elif code == 0 and language in {"java", "kotlin", "dotnet"}:
                candidates = [
                    Path("target/site/jacoco/jacoco.xml"),
                    Path("build/reports/jacoco/test/jacocoTestReport.xml"),
                    *_sorted_files("**/coverage.cobertura.xml"),
                ]
                report_path = _first_existing(candidates)
                coverage = _parse_xml_coverage(report_path) if report_path else None
                if coverage:
                    result["coverage"] = coverage
            elif code == 0 and language == "cpp":
                report_path = _first_existing(
                    [
                        Path("coverage.info"),
                        Path("build/coverage.info"),
                        *_sorted_files("**/lcov.info"),
                    ]
                )
                coverage = _parse_lcov(report_path) if report_path else None
                if coverage:
                    result["coverage"] = coverage
            elif code == 0 and language == "php":
                report_path = _first_existing(
                    [Path("coverage.xml"), Path("build/logs/clover.xml")]
                )
                coverage = _parse_xml_coverage(report_path) if report_path else None
                if coverage:
                    result["coverage"] = coverage
            elif code == 0 and language == "ruby":
                report_path = _first_existing(_sorted_files("coverage/.resultset.json"))
                coverage = _parse_simplecov(report_path) if report_path else None
                if coverage:
                    result["coverage"] = coverage
            return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
