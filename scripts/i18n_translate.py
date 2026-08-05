#!/usr/bin/env python3
"""Apply translations produced by the built-in translate_text tool.

Input JSONL format, one translation per line:
{"key":"auto....","locale":"en","text":"..."}

The script performs no network access. It validates protected tokens before
atomically updating the migration catalog.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"__UAG_PROTECTED_\d+__")


def tokens(value: object) -> list[str]:
    return sorted(TOKEN_RE.findall(value if isinstance(value, str) else ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply validated I18N translations.")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("translations", type=Path, help="JSONL from translate_text processing")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data: dict[str, Any] = json.loads(args.catalog.read_text(encoding="utf-8"))
    accepted = 0
    rejected: list[str] = []
    for line_no, line in enumerate(args.translations.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            key = str(item["key"])
            locale = str(item["locale"])
            text = str(item["text"])
            entry = data["entries"][key]
            if locale == "ja" or locale not in data["locales"]:
                raise ValueError("unsupported locale")
            if entry.get("risk") == "code_or_template":
                raise ValueError("code/template entries require manual review")
            if tokens(text) != tokens(entry.get("source_masked", "")):
                raise ValueError("protected token mismatch")
            if not args.dry_run:
                entry.setdefault("translations", {})[locale] = text
            accepted += 1
        except Exception as exc:
            rejected.append(f"line {line_no}: {exc}")

    if not args.dry_run and not rejected:
        tmp = args.catalog.with_suffix(args.catalog.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(args.catalog)
    print(json.dumps({"accepted": accepted, "rejected": rejected, "dry_run": args.dry_run}, ensure_ascii=False, indent=2))
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
