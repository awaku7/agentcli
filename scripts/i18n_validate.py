#!/usr/bin/env python3
"""Validate translated I18N catalogs without modifying source files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"__UAG_PROTECTED_\d+__")
LANG_RE = re.compile(r"^[a-z]{2,3}(?:_[A-Z]{2})?$")
LOCALE_CANDIDATE_RE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z]{2})?$")
SUPPORTED_TOOL_LOCALES = frozenset(
    {
        "ar", "bn", "cs", "da", "de", "el", "en", "es", "fa", "fi", "fil",
        "fr", "he", "hi", "hu", "id", "it", "ja", "ko", "mn", "mr", "ms",
        "nb", "nl", "nn", "pl", "pt", "pt_BR", "ro", "ru", "sv", "sw", "th",
        "tr", "uk", "vi", "zh_CN", "zh_TW",
    }
)


def tokens(value: object) -> list[str]:
    return sorted(TOKEN_RE.findall(value if isinstance(value, str) else ""))


def _validate_translation_manifest(data: dict[str, Any]) -> dict[str, Any]:
    locales = data.get("locales", [])
    entries = data.get("entries", {})
    errors: list[str] = []
    checked = 0
    if not isinstance(locales, list) or not isinstance(entries, dict):
        return {
            "mode": "translation_manifest",
            "checked_translations": 0,
            "errors": ["invalid translation manifest shape"],
            "ok": False,
        }
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            errors.append(f"{key}: entry must be an object")
            continue
        source = entry.get("source_masked", "")
        expected = tokens(source)
        translations = entry.get("translations", {})
        if not isinstance(translations, dict):
            errors.append(f"{key}: translations must be an object")
            continue
        for locale in locales:
            if locale == "ja":
                continue
            value = translations.get(locale, "")
            if not value:
                continue
            checked += 1
            actual = tokens(value)
            if actual != expected:
                errors.append(
                    f"{key}/{locale}: protected tokens differ: "
                    f"{expected} != {actual}"
                )
    return {
        "mode": "translation_manifest",
        "checked_translations": checked,
        "errors": errors,
        "ok": not errors,
    }


def _looks_like_tool_catalog(
    data: dict[str, Any], *, has_python_source: bool = False
) -> bool:
    if not data:
        return False
    keys = set(data)
    locale_candidates = {
        key for key in keys if isinstance(key, str) and LOCALE_CANDIDATE_RE.fullmatch(key)
    }
    if locale_candidates == keys:
        return True
    return has_python_source and bool(locale_candidates)


def _validate_tool_catalog(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if "en" in data:
        errors.append("tool JSON must not contain an 'en' block")
    for locale, block in sorted(data.items()):
        if not LANG_RE.fullmatch(locale):
            errors.append(f"{locale}: invalid locale key")
        elif locale not in SUPPORTED_TOOL_LOCALES:
            errors.append(f"{locale}: unsupported locale key")
        if not isinstance(block, dict):
            errors.append(f"{locale}: locale block must be an object")
    return {
        "mode": "tool_catalog",
        "checked_locales": len(data),
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate translation manifests or tool-side I18N JSON catalogs."
    )
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args()

    try:
        data = json.loads(args.catalog.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result = {"mode": "json", "errors": [str(exc)], "ok": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if not isinstance(data, dict):
        result = {"mode": "json", "errors": ["root must be an object"], "ok": False}
    elif "locales" in data or "entries" in data:
        result = _validate_translation_manifest(data)
    elif _looks_like_tool_catalog(
        data, has_python_source=args.catalog.with_suffix(".py").is_file()
    ):
        result = _validate_tool_catalog(data)
    else:
        result = {
            "mode": "non_i18n_json",
            "checked_locales": 0,
            "errors": [],
            "ok": True,
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
