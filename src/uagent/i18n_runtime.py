from __future__ import annotations

"""Runtime lookup for the protected I18N migration catalog.

The catalog is optional. Missing or invalid entries fall back to the caller's
English default, so enabling this module cannot break existing execution.
"""

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"__UAG_PROTECTED_(\d+)__")


def _language() -> str:
    value = (os.getenv("UAGENT_LANG") or os.getenv("LANG") or "en").split(".", 1)[0]
    value = value.replace("-", "_")
    if value.lower().startswith("pt_br"):
        return "pt_BR"
    if value.lower().startswith("zh_tw") or value.lower().startswith("zh_hant"):
        return "zh_TW"
    if value.lower().startswith("zh"):
        return "zh_CN"
    return value.split("_", 1)[0].lower() or "en"


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    path = Path(os.getenv("UAGENT_I18N_CATALOG", Path(__file__).with_name("i18n_catalog.json")))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def clear_cache() -> None:
    _catalog.cache_clear()


def translate(key: str, default: str = "", **values: Any) -> str:
    """Return a locale-specific translation with safe fallback and formatting."""
    data = _catalog()
    entry = data.get("entries", {}).get(key, {})
    locale = _language()
    value = ""
    if isinstance(entry, dict):
        translations = entry.get("translations", {})
        if isinstance(translations, dict):
            value = translations.get(locale) or translations.get("en") or ""
        value = value or entry.get("source_ja", "")
    value = str(value or default)
    protected = entry.get("protected_tokens", []) if isinstance(entry, dict) else []
    if values:
        try:
            value = value.format(**values)
        except (KeyError, IndexError, ValueError):
            pass
    for item in protected if isinstance(protected, list) else []:
        if isinstance(item, dict) and item.get("token") in value:
            value = value.replace(str(item["token"]), str(item.get("value", "")))
    return value
