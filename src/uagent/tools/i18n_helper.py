from __future__ import annotations

import json
import locale
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from ..i18n import detect_lang, get_thread_lang


def get_locale() -> str:
    """Return active locale (thread-local override or detected default)."""
    return get_thread_lang() or detect_lang()


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


def _unescape_newlines(s: str) -> str:
    # Allow translation JSON strings to contain literal backslash-n sequences
    # and have them rendered as real newlines in prompts/logs.
    return s.replace("\\r\\n", "\n").replace("\\n", "\n")


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
                return _unescape_newlines(v)

        # 2) fallback en
        en_map = data.get("en")
        if isinstance(en_map, dict):
            v = en_map.get(key)
            if isinstance(v, str) and v:
                return _unescape_newlines(v)

        # 3) final fallback: default embedded in code
        return default

    return _
