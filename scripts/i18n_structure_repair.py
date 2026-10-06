#!/usr/bin/env python3
"""Repair placeholder mismatches in localized tool search terms.

English source text lives in the matching Python file via
``_("x_search_terms", default=[...])``. Tool JSON contains non-English
translations only. Locale-specific search-term counts are intentionally
preserved.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
from pathlib import Path
from string import Formatter
from typing import Any

TARGET_LOCALES = frozenset(
    {
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
    }
)
_PRINTF_PLACEHOLDER_RE = re.compile(
    r"%\((?P<name>[A-Za-z0-9_]+)\)[#0 +\-]?[0-9]*(?:\.[0-9]+)?[diouxXeEfFgGcrs]"
)
_FORMATTER = Formatter()
_BRACE_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _placeholder_names(value: object) -> set[str]:
    text = str(value or "")
    names = {
        match.group("name") for match in _PRINTF_PLACEHOLDER_RE.finditer(text)
    }
    try:
        for _literal, field_name, _format_spec, _conversion in _FORMATTER.parse(text):
            if field_name is not None and _BRACE_FIELD_NAME_RE.fullmatch(field_name):
                names.add(field_name)
    except ValueError:
        names.add("<invalid-brace-format>")
    return names


def _english_search_terms(path: Path) -> list[str] | None:
    py_path = path.with_suffix(".py")
    if not py_path.is_file():
        return None
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_" or not node.args:
            continue
        key = node.args[0]
        if not isinstance(key, ast.Constant) or key.value != "x_search_terms":
            continue
        default_node = next(
            (kw.value for kw in node.keywords if kw.arg == "default"),
            None,
        )
        if default_node is None:
            continue
        try:
            value: Any = ast.literal_eval(default_node)
        except (ValueError, TypeError, SyntaxError):
            continue
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return value
    return None


def repair_file(path: Path, *, apply: bool) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    terms = _english_search_terms(path)
    if not terms:
        return False

    changed = False
    for lang, block in data.items():
        if lang not in TARGET_LOCALES or not isinstance(block, dict):
            continue
        current = block.get("x_search_terms")
        if not isinstance(current, list):
            continue
        normalized = list(current)
        for index in range(min(len(normalized), len(terms))):
            english_term = terms[index]
            if _placeholder_names(normalized[index]) != _placeholder_names(english_term):
                normalized[index] = english_term
        if normalized != current:
            block["x_search_terms"] = normalized
            changed = True

    if not changed or not apply:
        return changed
    backup = path.with_suffix(path.suffix + ".structure.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("src/uagent/tools"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = 0
    for path in sorted(args.root.glob("*.json")):
        if repair_file(path, apply=args.apply):
            changed += 1
            print(path)
    print(f"changed_files={changed} applied={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
