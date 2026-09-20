#!/usr/bin/env python3
"""Normalize tool search-term catalog structure without translating text.

The structural audit treats ``x_search_terms`` as an array-shaped catalog
value. Missing terms fall back to the English term at the same index and extra
terms are removed. Other values and catalog keys are left untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

_PLACEHOLDER_RE = re.compile(
    r"(?:%\(([A-Za-z0-9_]+)\)[^%]*|\{([A-Za-z_][A-Za-z0-9_]*)\})"
)


def _placeholder_names(value: object) -> set[str]:
    return {
        first or second for first, second in _PLACEHOLDER_RE.findall(str(value or ""))
    }


def repair_file(path: Path, *, apply: bool) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    english = data.get("en")
    if not isinstance(english, dict) or not isinstance(
        english.get("x_search_terms"), list
    ):
        return False
    terms = english["x_search_terms"]
    changed = False
    for lang, block in data.items():
        if lang == "en" or not isinstance(block, dict):
            continue
        current = block.get("x_search_terms")
        if not isinstance(current, list):
            continue
        normalized = list(current[: len(terms)])
        normalized.extend(terms[len(normalized) :])
        for index, english_term in enumerate(terms):
            if _placeholder_names(normalized[index]) != _placeholder_names(
                english_term
            ):
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
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("src/uagent/tools"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = 0
    for path in sorted(args.root.glob("*_tool.json")):
        if repair_file(path, apply=args.apply):
            changed += 1
            print(path)
    print(f"changed_files={changed} applied={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
