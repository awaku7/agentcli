from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional


def _normalize_locale(locale: Optional[str]) -> str:
    """Normalize locale strings.

    Examples:
      - 'ja_JP' -> 'ja'
      - 'en-US' -> 'en'
      - None / '' -> 'en'
    """
    if not locale:
        return "en"
    s = str(locale).strip()
    if not s:
        return "en"
    s = s.replace("-", "_")
    base = s.split("_")[0].lower()
    return base or "en"


def get_locale() -> str:
    """Return active locale based on UAGENT_LOCALE.

    This project requirement is to rely on UAGENT_LOCALE.
    """
    return _normalize_locale(os.environ.get("UAGENT_LOCALE"))


@lru_cache(maxsize=256)
def _load_tool_dict(json_path: str) -> Dict[str, Any]:
    """Load tool-localization JSON.

    Expected format:
      {
        "en": {"key": "text", ...},
        "ja": {"key": "text", ...}
      }

    If file doesn't exist or is invalid, returns empty dict.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except FileNotFoundError:
        return {}
    except Exception:
        # Do not crash tool import due to i18n issues
        return {}


def make_tool_translator(tool_py_file: str):
    """Create a translator function for a tool module.

    Rules:
    - JSON file is alongside the tool module: <tool>.py -> <tool>.json
    - Locale from UAGENT_LOCALE (normalized to base language like 'en', 'ja')
    - Fallback order: requested-locale -> en -> default

    Usage:
      _ = make_tool_translator(__file__)
      desc = _("tool.description", default="Read file ...")
    """

    tool_dir = os.path.dirname(os.path.abspath(tool_py_file))
    base = os.path.splitext(os.path.basename(tool_py_file))[0]
    json_path = os.path.join(tool_dir, f"{base}.json")

    def _(key: str, *, default: str) -> str:
        locale = get_locale()
        data = _load_tool_dict(json_path)

        # 1) requested locale
        loc_map = data.get(locale)
        if isinstance(loc_map, dict):
            v = loc_map.get(key)
            if isinstance(v, str) and v:
                return v

        # 2) fallback en
        en_map = data.get("en")
        if isinstance(en_map, dict):
            v = en_map.get(key)
            if isinstance(v, str) and v:
                return v

        # 3) final fallback: default embedded in code
        return default

    return _
