#!/usr/bin/env python3
"""Validate translated I18N catalogs without modifying source files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"__UAG_PROTECTED_\d+__")


def tokens(value: object) -> list[str]:
    return sorted(TOKEN_RE.findall(value if isinstance(value, str) else ""))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate I18N translations and protected tokens."
    )
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()
    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    locales = data.get("locales", [])
    errors: list[str] = []
    checked = 0
    for key, entry in data.get("entries", {}).items():
        source = entry.get("source_masked", "")
        expected = tokens(source)
        for locale in locales:
            if locale == "ja":
                continue
            value = entry.get("translations", {}).get(locale, "")
            if not value:
                continue
            checked += 1
            actual = tokens(value)
            if actual != expected:
                errors.append(
                    f"{key}/{locale}: protected tokens differ: {expected} != {actual}"
                )
    result = {"checked_translations": checked, "errors": errors, "ok": not errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
