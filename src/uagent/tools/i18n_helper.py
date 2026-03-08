from __future__ import annotations

import json
import os
from ..env_utils import env_get
import locale
from functools import lru_cache
from typing import Any, Dict, Optional


def _normalize_locale(loc_str: Optional[str]) -> str:
    """Normalize locale strings.

    Examples:
      - 'ja_JP' -> 'ja'
      - 'en-US' -> 'en'
      - None / '' -> 'en'
    """
    if not loc_str:
        return "en"
    s = str(loc_str).strip()
    if not s:
        return "en"
    s = s.replace("-", "_")
    # Drop encoding and modifiers
    s = s.split(".")[0].split("@")[0]
    base = s.split("_")[0].lower()

    # Common aliases
    if base in ("us",):
        base = "en"
    if base in ("jp",):
        base = "ja"

    if base.startswith("ja"):
        return "ja"
    return base or "en"


def get_locale() -> str:
    """Return active locale based on environment or OS settings.

    Priority:
      1) UAGENT_LANG (explicit override)
      2) LC_ALL / LANG (standard env vars)
      3) OS default locale (via locale module)
    """

    # 1) explicit override
    v = (env_get("UAGENT_LANG") or "").strip()
    if v:
        return _normalize_locale(v)

    # 2) common env vars
    for k in ("LC_ALL", "LANG"):
        vv = (env_get(k) or "").strip()
        if vv:
            return _normalize_locale(vv)

    # 3) OS locale
    try:
        loc, _enc = locale.getlocale()
        if loc:
            return _normalize_locale(loc)
    except Exception:
        pass

    try:
        # getdefaultlocale is deprecated but serves as a fallback
        loc2 = None
        try:
            loc2, _enc2 = locale.getdefaultlocale()  # type: ignore[attr-defined]
        except Exception:
            loc2 = None
        if loc2:
            return _normalize_locale(loc2)
    except Exception:
        pass

    return "en"


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
    - Locale is detected from environment or OS (normalized to 'en', 'ja', etc.)
    - Fallback order: detected-locale -> en -> default

    Usage:
      _ = make_tool_translator(__file__)
      desc = _("tool.description", default="Read file ...")
    """

    tool_dir = os.path.dirname(os.path.abspath(tool_py_file))
    base = os.path.splitext(os.path.basename(tool_py_file))[0]
    json_path = os.path.join(tool_dir, f"{base}.json")

    def _(key: str, *, default: str) -> str:
        loc = get_locale()
        data = _load_tool_dict(json_path)

        # 1) requested locale
        loc_map = data.get(loc)
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
