"""Review the current Git worktree without modifying it."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)
BUSY_LABEL = False
STATUS_LABEL = "tool:git_review"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "devel",
    "type": "function",
    "function": {
        "name": "git_review",
        "description": _(
            "tool.description",
            default="Review Git changes, risky files, and possible secrets without modifying the repository.",
        ),
        "x_search_terms": [
            "git review",
            "git diff review",
            "変更レビュー",
            "秘密情報検出",
            "code review",
        ],
        "x_search_terms_en": [
            "git review",
            "git diff review",
            "changed files",
            "secret scan",
            "code review",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": _(
                        "param.staged.description",
                        default="Review staged changes instead of unstaged changes.",
                    ),
                    "default": False,
                },
                "include_untracked": {
                    "type": "boolean",
                    "description": _(
                        "param.include_untracked.description",
                        default="Include untracked files in the review.",
                    ),
                    "default": True,
                },
                "scan_secrets": {
                    "type": "boolean",
                    "description": _(
                        "param.scan_secrets.description",
                        default="Scan changed text files for likely secrets without returning secret values.",
                    ),
                    "default": True,
                },
                "max_files": {
                    "type": "integer",
                    "description": _(
                        "param.max_files.description",
                        default="Maximum number of changed files to inspect.",
                    ),
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
            },
        },
    },
}

_SECRET_PATTERNS = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "api_key_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"]?[^\s'\"]{12,}"
        ),
    ),
    (
        "provider_key",
        re.compile(
            r"\b(?:OPENAI|ANTHROPIC|GOOGLE|AWS|AZURE|GITHUB|SLACK)_[A-Z0-9_]*(?:KEY|TOKEN|SECRET)\b\s*="
        ),
    ),
)
_RISKY_NAMES = (
    ".env",
    ".pem",
    ".key",
    "credentials",
    "secret",
    "token",
    "id_rsa",
    ".github/workflows/",
)


def _run_git(args: list[str]) -> tuple[bool, str, str]:
    env = os.environ.copy()
    env.update({"GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": ":"})
    try:
        p = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=30,
        )
        return p.returncode == 0, p.stdout, p.stderr
    except Exception as exc:
        return False, "", str(exc)


def _changed_files(staged: bool, include_untracked: bool) -> list[dict[str, str]]:
    ok, out, err = _run_git(["status", "--porcelain=v1"])
    if not ok:
        raise RuntimeError(err or "git status failed")
    result: list[dict[str, str]] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        xy, path = line[:2], line[3:]
        if staged and xy[0] == " ":
            continue
        if not staged and xy[1] == " " and xy[0] != "?":
            continue
        if xy == "??" and not include_untracked:
            continue
        result.append({"path": path, "status": xy})
    return result


def _test_candidates(files: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Find conventional pytest files related to changed source files."""
    candidates: list[dict[str, Any]] = []
    tests_root = Path("tests")
    for item in files:
        path = Path(item["path"])
        if path.parts and path.parts[0].lower() in {"tests", "test"}:
            continue
        stem = path.stem
        patterns = [f"test_{stem}.py", f"test_{stem}_*.py"]
        matches: list[str] = []
        if tests_root.is_dir():
            for pattern in patterns:
                matches.extend(
                    p.as_posix() for p in tests_root.rglob(pattern) if p.is_file()
                )
        candidates.append({"source": item["path"], "tests": sorted(set(matches))})
    return candidates


def _scan_file(path_text: str) -> list[dict[str, Any]]:
    path = Path(path_text)
    if not path.is_file() or path.stat().st_size > 2_000_000:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for kind, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"path": path_text, "line": line_no, "kind": kind})
                break
    return findings


def run_tool(args: dict[str, Any]) -> str:
    try:
        staged = bool(args.get("staged", False))
        include_untracked = bool(args.get("include_untracked", True))
        scan_secrets = bool(args.get("scan_secrets", True))
        max_files = int(args.get("max_files", 100))
        if not 1 <= max_files <= 1000:
            raise ValueError("max_files must be between 1 and 1000")
        files = _changed_files(staged, include_untracked)[:max_files]
        diff_args = ["diff", "--cached"] if staged else ["diff"]
        ok, stat, err = _run_git([*diff_args, "--stat"])
        if not ok:
            raise RuntimeError(err or "git diff failed")
        ok, numstat, _ = _run_git([*diff_args, "--numstat"])
        additions = deletions = 0
        if ok:
            for line in numstat.splitlines():
                parts = line.split("\t", 2)
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    additions += int(parts[0])
                    deletions += int(parts[1])
        risky = [
            f["path"]
            for f in files
            if any(x in f["path"].lower() for x in _RISKY_NAMES)
        ]
        findings = []
        if scan_secrets:
            for f in files:
                # Scan the working-tree content for both tracked and untracked files.
                # For staged review this also catches secrets that remain in the file.
                findings.extend(_scan_file(f["path"]))
        return json.dumps(
            {
                "ok": True,
                "staged": staged,
                "files": files,
                "file_count": len(files),
                "additions": additions,
                "deletions": deletions,
                "diff_stat": stat.strip(),
                "risky_files": risky,
                "test_candidates": _test_candidates(files),
                "secret_findings": findings,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
