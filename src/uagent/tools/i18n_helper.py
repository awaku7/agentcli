from __future__ import annotations

import json
import locale
import os
from functools import lru_cache
from typing import Any, Optional

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
    """Detect runtime language with same fallback chain as uagent.i18n.

    Priority:
    1) UAGENT_LANG env var
    2) LC_ALL / LANG env vars
    3) locale.getlocale()
    4) locale.getdefaultlocale()
    5) Windows console code page (os.name == 'nt')
    6) 'en'
    """
    # 1) explicit override
    v = (env_get("UAGENT_LANG") or "").strip()
    if v:
        return _normalize_lang_tag(v)

    # 2) common env vars
    for k in ("LC_ALL", "LANG"):
        vv = (env_get(k) or "").strip()
        if vv:
            return _normalize_lang_tag(vv)

    # 3) Python locale
    try:
        loc, _enc = locale.getlocale()
        if loc:
            return _normalize_lang_tag(loc)
    except Exception:
        pass

    # 4) getdefaultlocale (deprecated but available)
    try:
        loc2 = None
        try:
            loc2, _enc2 = locale.getdefaultlocale()  # type: ignore[attr-defined]
        except Exception:
            loc2 = None
        if loc2:
            return _normalize_lang_tag(loc2)
    except Exception:
        pass

    # 5) Windows console code page
    if os.name == "nt":
        vcp = _detect_windows_console_lang()
        if vcp:
            return _normalize_lang_tag(vcp)

    return "en"


def _detect_windows_console_lang() -> str | None:
    """Detect language from Windows console code page."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        cp_map = {
            932: "ja",
            936: "zh_CN",
            949: "ko",
            950: "zh_TW",
            874: "th",
            1258: "vi",
        }
        if cp in cp_map:
            return cp_map[cp]

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        lang_map = {
            0x09: "en",
            0x11: "ja",
            0x12: "ko",
            0x04: "zh_CN",
            0x07: "de",
            0x0C: "fr",
            0x0A: "es",
            0x10: "it",
            0x16: "pt",
            0x13: "nl",
            0x1D: "sv",
            0x14: "nb",
            0x0B: "fi",
            0x01: "ar",
            0x29: "fa",
            0x15: "pl",
            0x05: "cs",
            0x19: "ru",
            0x22: "uk",
            0x1F: "tr",
            0x2A: "vi",
            0x1E: "th",
            0x21: "id",
            0x45: "bn",
            0x39: "hi",
            0x4E: "mr",
            0x50: "mn",
            0x41: "sw",
        }
        if lang_id in lang_map:
            return lang_map[lang_id]
    except Exception:
        pass
    return None


def get_locale() -> str:
    return detect_lang()


@lru_cache(maxsize=256)
def _load_tool_dict(json_path: str) -> dict[str, Any]:
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
