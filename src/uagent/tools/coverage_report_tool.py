"""Run supported project coverage commands with a normalized result."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
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
                    "enum": ["auto", "python", "typescript", "rust", "go"],
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
    if (
        (root / "pyproject.toml").exists()
        or (root / "pytest.ini").exists()
        or list(root.glob("**/*.py"))
    ):
        return "python"
    if (root / "package.json").exists() or list(root.glob("**/*.ts")):
        return "typescript"
    if (root / "Cargo.toml").exists():
        return "rust"
    if (root / "go.mod").exists():
        return "go"
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
            ["npx", "--no-install", "c8", "npm", "test"],
            "npx --no-install c8 npm test",
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
        if requested not in {"auto", "python", "typescript", "rust", "go"}:
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
            return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
