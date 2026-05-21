from __future__ import annotations

import json
import locale
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from ..env_utils import env_get


def _normalize_lang_tag(tag: Optional[str]) -> str:
    if not tag:
        return "en"

    t = str(tag).strip().lower()
    if not t:
        return "en"

    t = t.split(".", 1)[0].split("@", 1)[0]
    t = t.replace("-", "_")

    if t.startswith("ja"):
        return "ja"
    if t.startswith("zh"):
        if "tw" in t or "hant" in t or "hk" in t or "mo" in t:
            return "zh_TW"
        return "zh_CN"
    if t.startswith("pt"):
        return "pt_BR" if "br" in t else "pt"
    if t.startswith("hi"):
        return "hi"

    return t.split("_", 1)[0] or "en"


def detect_lang() -> str:
    for var in ("UAGENT_LANG", "LC_ALL", "LANG"):
        candidate = env_get(var)
        if candidate:
            return _normalize_lang_tag(candidate)

    candidate = locale.getlocale()[0]
    if candidate:
        return _normalize_lang_tag(candidate)

    return "en"


def get_locale() -> str:
    return detect_lang()


@lru_cache(maxsize=256)
def _load_tool_dict(json_path: str) -> Dict[str, Any]:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


def clear_tool_i18n_cache() -> None:
    """Clear cached tool translation JSON data."""
    try:
        _load_tool_dict.cache_clear()
    except Exception:
        pass


def _unescape_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\\r\\n", "\n").replace("\\n", "\n")
    if isinstance(value, list):
        return [_unescape_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _unescape_value(v) for k, v in value.items()}
    return value


def make_tool_translator(tool_py_file: str):
    tool_dir = os.path.dirname(os.path.abspath(tool_py_file))
    base = os.path.splitext(os.path.basename(tool_py_file))[0]
    json_path = os.path.join(tool_dir, f"{base}.json")

    def _(key: str, *, default: Any, **kwargs: object) -> Any:
        loc = get_locale()
        data = _load_tool_dict(json_path)

        text = None
        loc_map = data.get(loc)
        if isinstance(loc_map, dict):
            v = loc_map.get(key)
            if isinstance(v, (str, list, dict)) and v:
                text = _unescape_value(v)

        if text is None:
            en_map = data.get("en")
            if isinstance(en_map, dict):
                v = en_map.get(key)
                if isinstance(v, (str, list, dict)) and v:
                    text = _unescape_value(v)

        if text is None:
            text = default

        if kwargs:
            candidates = [text]
            if default != text:
                candidates.append(default)
            for candidate in candidates:
                if "%(" in candidate:
                    try:
                        return candidate % kwargs
                    except Exception:
                        pass
                try:
                    return candidate.format(**kwargs)
                except Exception:
                    try:
                        return candidate % kwargs
                    except Exception:
                        pass

        return text

    return _
