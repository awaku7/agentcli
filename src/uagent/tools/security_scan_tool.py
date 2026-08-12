"""Read-only repository security checks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)
BUSY_LABEL = False
STATUS_LABEL = "tool:security_scan"

TOOL_SPEC: dict[str, Any] = {
    "tool_genre": "devel",
    "type": "function",
    "function": {
        "name": "security_scan",
        "description": _(
            "tool.description",
            default="Scan repository files for likely secrets and risky configuration files without returning secret values.",
        ),
        "x_search_terms": [
            "security scan",
            "secret scan",
            "脆弱性検査",
            "秘密情報検出",
            "セキュリティ検査",
        ],
        "x_search_terms_en": [
            "security scan",
            "secret scan",
            "credentials",
            "private key",
            "risky config",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": _(
                        "param.root.description",
                        default="Directory to scan, relative to the current workdir.",
                    ),
                    "default": ".",
                },
                "max_files": {
                    "type": "integer",
                    "description": _(
                        "param.max_files.description",
                        default="Maximum number of files to inspect.",
                    ),
                    "default": 1000,
                    "minimum": 1,
                    "maximum": 10000,
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": _(
                        "param.include_hidden.description",
                        default="Include hidden files and directories.",
                    ),
                    "default": False,
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
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"]?[^\s'\"]{12,}"
        ),
    ),
    (
        "provider_key_assignment",
        re.compile(
            r"\b(?:OPENAI|ANTHROPIC|GOOGLE|AWS|AZURE|GITHUB|SLACK)_[A-Z0-9_]*(?:KEY|TOKEN|SECRET)\b\s*="
        ),
    ),
)
_RISKY_NAMES = (".env", ".pem", ".key", "credentials", "secret", "token", "id_rsa")
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _scan_file(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for kind, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {"path": path.as_posix(), "line": line_no, "kind": kind}
                )
                break
    return findings


def _files(root: Path, include_hidden: bool, max_files: int) -> tuple[list[Path], bool]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if not include_hidden and _is_hidden(rel):
            continue
        result.append(path)
    return result[:max_files], len(result) > max_files


def run_tool(args: dict[str, Any]) -> str:
    try:
        root = Path(str(args.get("root", ".") or ".")).resolve()
        max_files = int(args.get("max_files", 1000))
        include_hidden = bool(args.get("include_hidden", False))
        if not 1 <= max_files <= 10000:
            raise ValueError("max_files must be between 1 and 10000")
        workdir = Path.cwd().resolve()
        if root != workdir and workdir not in root.parents:
            raise ValueError("root must be inside the current workdir")
        if not root.is_dir():
            raise ValueError("root must be an existing directory")
        files, truncated = _files(root, include_hidden, max_files)
        findings: list[dict[str, Any]] = []
        risky_files: list[str] = []
        for path in files:
            rel = path.relative_to(root).as_posix()
            lower = rel.lower()
            if any(name in lower for name in _RISKY_NAMES):
                risky_files.append(rel)
            findings.extend(_scan_file(path))
        return json.dumps(
            {
                "ok": True,
                "root": root.as_posix(),
                "scanned_files": len(files),
                "truncated": truncated,
                "risky_files": sorted(set(risky_files)),
                "secret_findings": findings,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
