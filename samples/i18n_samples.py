#!/usr/bin/env python
from __future__ import annotations

import json
import locale
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LOCALE_DIR = ROOT / "locale"
_CACHE: dict[str, dict[str, str]] = {}


def _detect_lang() -> str:
    lang = (
        os.environ.get("UAGENT_LANG")
        or os.environ.get("LANG")
        or os.environ.get("LC_ALL")
        or os.environ.get("LC_MESSAGES")
    )
    if not lang:
        try:
            loc, _enc = locale.getlocale()
            lang = loc or ""
        except Exception:
            lang = ""
    if not lang:
        try:
            loc2, _enc2 = locale.getdefaultlocale()  # type: ignore[attr-defined]
            lang = loc2 or ""
        except Exception:
            lang = ""
    if not lang:
        lang = "en"
    lang = lang.split(".")[0].split("@")[0]
    return lang.replace("-", "_")


def _normalize_lang(lang: str) -> str:
    lang = lang.lower()
    if lang.startswith("ja"):
        return "ja"
    if lang.startswith("zh_cn"):
        return "zh_CN"
    if lang.startswith("zh_tw"):
        return "zh_TW"
    if lang.startswith("ko"):
        return "ko"
    if lang.startswith("th"):
        return "th"
    if lang.startswith("es"):
        return "es"
    if lang.startswith("fr"):
        return "fr"
    return "en"


def _load_catalog(lang: str) -> dict[str, str]:
    lang = _normalize_lang(lang)
    if lang in _CACHE:
        return _CACHE[lang]

    path = LOCALE_DIR / f"{lang}.json"
    if not path.exists() and lang != "en":
        path = LOCALE_DIR / "en.json"

    data: dict[str, str] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    _CACHE[lang] = data
    return data


def _(key: str, default: str | None = None, **kwargs: Any) -> str:
    lang = _normalize_lang(_detect_lang())
    catalog = _load_catalog(lang)
    text = catalog.get(key, default if default is not None else key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text
