#!/usr/bin/env python3
"""Audit Python and tool catalogs for localization readiness.

This script is intentionally conservative: it never rewrites Python source or
pretends that copying English is a translation. It reports hard-coded Japanese
strings and checks tool sidecar catalogs against the project's 38 locale set.
Use --write-report to create a JSON report for a translation pass.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# English plus the 37 locale variants used by the documentation set.
SUPPORTED_LOCALES = (
    "en",
    "ar",
    "bn",
    "cs",
    "da",
    "de",
    "el",
    "es",
    "fa",
    "fi",
    "fil",
    "fr",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "ko",
    "mn",
    "mr",
    "ms",
    "nb",
    "nl",
    "nn",
    "pl",
    "pt",
    "pt_BR",
    "ro",
    "ru",
    "sv",
    "sw",
    "th",
    "tr",
    "uk",
    "vi",
    "zh_CN",
    "zh_TW",
)
JAPANESE_RE = re.compile(r"[ぁ-んァ-ヶ一-龯]")


@dataclass
class JapaneseLiteral:
    file: str
    line: int
    column: int
    text: str
    context: str


@dataclass
class CatalogFinding:
    file: str
    missing_locales: list[str]
    extra_locales: list[str]
    missing_keys: dict[str, list[str]]


def _literal_text(node: ast.Constant) -> str | None:
    return node.value if isinstance(node.value, str) else None


def _context(node: ast.AST) -> str:
    parent = getattr(node, "_uag_parent", None)
    if isinstance(parent, ast.keyword) and parent.arg:
        return parent.arg
    if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name):
        return parent.func.id
    return type(parent).__name__ if parent is not None else "module"


def scan_python(root: Path) -> list[JapaneseLiteral]:
    findings: list[JapaneseLiteral] = []
    for path in sorted(root.rglob("*.py")):
        if any(part == "__pycache__" or part.startswith(".") for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError) as exc:
            findings.append(
                JapaneseLiteral(str(path), 0, 0, f"<parse error: {exc}>", "parse")
            )
            continue
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                setattr(child, "_uag_parent", parent)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            text = _literal_text(node)
            if text is None or not JAPANESE_RE.search(text):
                continue
            findings.append(
                JapaneseLiteral(
                    file=str(path),
                    line=getattr(node, "lineno", 0),
                    column=getattr(node, "col_offset", 0),
                    text=text,
                    context=_context(node),
                )
            )
    return findings


def scan_catalogs(tool_dir: Path) -> list[CatalogFinding]:
    findings: list[CatalogFinding] = []
    expected = set(SUPPORTED_LOCALES)
    for path in sorted(tool_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "en" not in data:
            continue
        locales = {key for key, value in data.items() if isinstance(value, dict)}
        missing_locales = sorted(expected - locales)
        extra_locales = sorted(locales - expected)
        en_map = data.get("en", {})
        keys = set(en_map) if isinstance(en_map, dict) else set()
        missing_keys = {
            locale: sorted(keys - set(data.get(locale, {})))
            for locale in sorted(locales & expected)
            if isinstance(data.get(locale), dict) and keys - set(data.get(locale, {}))
        }
        if missing_locales or extra_locales or missing_keys:
            findings.append(
                CatalogFinding(str(path), missing_locales, extra_locales, missing_keys)
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Python i18n and 38-locale tool catalogs."
    )
    parser.add_argument("--root", type=Path, default=Path("src/uagent"))
    parser.add_argument("--tool-dir", type=Path, default=Path("src/uagent/tools"))
    parser.add_argument("--write-report", type=Path)
    parser.add_argument(
        "--strict", action="store_true", help="Return non-zero when findings exist."
    )
    args = parser.parse_args()

    literals = scan_python(args.root)
    catalogs = scan_catalogs(args.tool_dir)
    report: dict[str, Any] = {
        "supported_locale_count": len(SUPPORTED_LOCALES),
        "supported_locales": list(SUPPORTED_LOCALES),
        "python_japanese_literal_count": len(literals),
        "python_japanese_literals": [asdict(item) for item in literals],
        "catalog_issue_count": len(catalogs),
        "catalog_issues": [asdict(item) for item in catalogs],
    }
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 1 if args.strict and (literals or catalogs) else 0


if __name__ == "__main__":
    sys.exit(main())
