"""uagent.i18n

Lightweight i18n layer for user-facing messages.

Policy (stable / low-risk):
- Use gettext with domain 'uag'.
- Detect language from environment/OS locale.
- Locale selection rule (Plan A): if language starts with 'ja' -> 'ja', else 'en'.
- Fallback must never break runtime: if translations are missing, return msgid.

Language selection priority:
1) UAGENT_LANG (explicit override)
2) LC_ALL / LANG (common on Unix; may exist on Windows too)
3) Python locale module (getlocale/getdefaultlocale)

This module is intentionally dependency-free (stdlib only).
"""

from __future__ import annotations

import gettext
import locale
import os

from .env_utils import env_get
from functools import lru_cache
from typing import Optional

from pathlib import Path

import threading

# Thread-local language override (used by Web per-room locale)
_thread_lang = threading.local()


def set_thread_lang(lang: str | None) -> None:
    """Set thread-local language override.

    - Use 'ja' or 'en'.
    - Pass None or '' to clear override.
    """

    try:
        if not lang:
            if hasattr(_thread_lang, "lang"):
                delattr(_thread_lang, "lang")
            return
        setattr(_thread_lang, "lang", str(lang).strip().lower())
    except Exception:
        pass


def get_thread_lang() -> str | None:
    """Get thread-local language override (or None)."""

    try:
        v = getattr(_thread_lang, "lang", None)
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
    except Exception:
        pass
    return None


def _find_localedir_candidates() -> list[str]:
    """Return candidate locale directories.

    We support multiple run modes:
    - Installed package (site-packages)
    - Editable/source execution (python -m uagent)
    - Legacy launcher scripts that manipulate sys.path (python scheck.py)

    Strategy:
    1) <this_file_dir>/locales
    2) <repo_root>/src/uagent/locales (best-effort; derived from this file path)
    3) <cwd>/src/uagent/locales (common when running from repo root)
    """

    cands: list[str] = []

    # 1) Adjacent to this file (normal package layout)
    cands.append(str(Path(__file__).resolve().parent / "locales"))

    # 2) Repo-style: .../src/uagent/i18n.py -> .../src/uagent/locales
    try:
        here = Path(__file__).resolve()
        repo_style = here.parent / "locales"
        cands.append(str(repo_style))
    except Exception:
        pass

    # 3) CWD-style: ./src/uagent/locales
    try:
        cands.append(str(Path.cwd().resolve() / "src" / "uagent" / "locales"))
    except Exception:
        pass

    # de-dup while preserving order
    seen = set()
    out: list[str] = []
    for x in cands:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


DOMAIN = "uag"


def _available_catalog_langs() -> set[str]:
    # Return available catalog language codes by scanning locales directory.

    langs: set[str] = set()
    for cand in _find_localedir_candidates():
        base = Path(cand)
        if not base.is_dir():
            continue
        try:
            for p in base.glob("*/LC_MESSAGES/uag.mo"):
                try:
                    langs.add(p.parent.parent.name)  # <lang>/LC_MESSAGES/uag.mo
                except Exception:
                    pass
        except Exception:
            pass
    return langs


def _normalize_lang_tag(tag: Optional[str]) -> str:
    # Normalize various locale tags into a language code supported by our catalogs.
    #
    # Examples:
    #   - 'ja_JP', 'ja-JP', 'ja_JP.UTF-8' -> 'ja'
    #   - 'en_US', 'en-US' -> 'en'
    #   - 'zh_CN', 'zh-CN', 'zh_Hans', 'zh-Hans-CN' -> 'zh_CN'
    #   - 'zh_TW', 'zh-TW', 'zh_Hant', 'zh-Hant-TW' -> 'zh_TW'
    #
    # Notes:
    #   - This project may ship additional catalogs; we detect available ones by scanning locales.
    #   - Unknown / unsupported languages fall back to 'en' (must never break runtime).

    supported = _available_catalog_langs() | {"en"}  # always allow 'en' fallback

    if not tag:
        return "en"

    t = str(tag).strip()
    if not t:
        return "en"

    # Drop encoding ('.UTF-8') and modifiers ('@...')
    t = t.split(".", 1)[0].split("@", 1)[0]

    # Normalize delimiter
    t_norm = t.replace("-", "_")

    parts = [p for p in t_norm.split("_") if p]
    lang = parts[0].lower() if parts else ""
    script = None
    region = None

    # Handle Windows-style names (e.g., "Japanese_Japan", "Chinese_China")
    win_names = {
        "japanese": ("ja", None),
        "english": ("en", None),
        "german": ("de", None),
        "french": ("fr", None),
        "spanish": ("es", None),
        "italian": ("it", None),
        "arabic": ("ar", None),
        "portuguese": ("pt", None),
        "korean": ("ko", None),
        "russian": ("ru", None),
        "thai": ("th", None),
    }
    if lang in win_names:
        mapped_lang, mapped_script = win_names[lang]
        lang = mapped_lang
        if mapped_script:
            script = mapped_script

    if len(parts) >= 2:
        # script or region
        p1 = parts[1]
        if len(p1) == 4:
            script = p1.title()  # Hans/Hant
        else:
            region = p1.upper()
            # Special case for Windows "Chinese_China" -> region="CHINA"
            if region == "CHINA":
                region = "CN"
            elif region == "TAIWAN":
                region = "TW"
            elif "HONG KONG" in region:
                region = "HK"
            elif "MACAU" in region:
                region = "MO"

    if parts and parts[0].lower() == "chinese":
        lang = "zh"

    if len(parts) >= 3:
        # region if script present
        if script and not region:
            region = parts[2].upper()

    # 1) Map to base supported language codes
    target = "en"

    if lang == "ja":
        target = "ja"
    elif lang == "en":
        target = "en"
    elif lang == "zh":
        # Chinese: map Hans/Hant to CN/TW
        if region in {"CN", "SG"} or script == "Hans":
            target = "zh_CN"
        elif region in {"TW", "HK", "MO"} or script == "Hant":
            target = "zh_TW"
        else:
            target = "zh_CN"  # Default zh to CN
    elif lang == "pt":
        # Portuguese: prefer pt for generic/European Portuguese, pt_BR for Brazil.
        if region == "BR":
            target = "pt_BR" if "pt_BR" in supported else "pt"
        else:
            target = "pt" if "pt" in supported else "pt_BR"
    else:
        # Generic: use the language code itself (fr, de, ko, etc.)
        target = lang

    # 2) Final fallback check: if requested lang is not in supported catalogs,
    # try simpler fallbacks before giving up to "en".
    if target in supported:
        return target

    # 'zh_CN' -> 'zh' (if 'zh' was supported but not 'zh_CN')
    # 'pt_BR' -> 'pt'
    if "_" in target:
        base = target.split("_")[0]
        if base in supported:
            return base

    return "en"


def _detect_windows_console_lang() -> str | None:
    """Detect language from Windows console code page."""
    if os.name != "nt":
        return None

    try:
        import ctypes

        # https://learn.microsoft.com/en-us/windows/win32/api/wincon/nf-wincon-getconsoleoutputcp
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        # Map common Windows console code pages to language codes
        # https://learn.microsoft.com/en-us/windows/win32/intl/code-page-identifiers
        # Map Windows code pages to supported language codes
        # https://learn.microsoft.com/en-us/windows/win32/intl/code-page-identifiers
        cp_map = {
            932: "ja",  # Japanese
            936: "zh_CN",  # Simplified Chinese
            949: "ko",  # Korean
            950: "zh_TW",  # Traditional Chinese
            1251: "ru",  # Cyrillic (Russian)
            874: "th",  # Thai
            # Western European (1252/850) can be any of en, de, fr, es, it, pt.
            # Without further API calls, we default to "en" for these code pages.
            1252: "en",
            850: "en",
            437: "en",
        }
        if cp in cp_map:
            return cp_map[cp]

        # For Western European or others, try User Default UI Language as a fallback
        # https://learn.microsoft.com/en-us/windows/win32/api/winnls/nf-winnls-getuserdefaultuilanguage
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        lang_map = {
            0x07: "de",  # German
            0x0C: "fr",  # French
            0x0A: "es",  # Spanish
            0x10: "it",  # Italian
            0x01: "ar",  # Arabic
            0x16: "pt",  # Portuguese (pt_BR)
        }
        if lang_id in lang_map:
            return lang_map[lang_id]
    except Exception:
        pass
    return None


def detect_lang() -> str:
    """Detect runtime language.

    Returns:
      Detected language code (e.g., 'ja', 'en', 'zh_CN').
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

    try:
        # getdefaultlocale is deprecated in newer Python but still available.
        loc2 = None
        try:
            loc2, _enc2 = locale.getdefaultlocale()  # type: ignore[attr-defined]
        except Exception:
            loc2 = None
        if loc2:
            return _normalize_lang_tag(loc2)
    except Exception:
        pass

    if os.name == "nt":
        vcp = _detect_windows_console_lang()
        if vcp:
            # We trust _detect_windows_console_lang's mapping but normalize
            # just in case to ensure it's in our supported set.
            return _normalize_lang_tag(vcp)

    return "en"


@lru_cache(maxsize=8)
def _get_translation(lang: str) -> gettext.NullTranslations:
    """Return gettext translation object for given lang.

    Fallback behavior:
    - If locale directory or catalog is missing, returns NullTranslations.
    """

    # The locale directory is packaged under uagent/locales
    # But launchers may manipulate sys.path (e.g., python scheck.py).
    # So we search multiple candidate directories and use the first existing one.
    localedir = None
    for cand in _find_localedir_candidates():
        if os.path.isdir(cand):
            localedir = cand
            break
    if localedir is None:
        localedir = os.path.join(os.path.dirname(__file__), "locales")

    try:
        return gettext.translation(
            DOMAIN,
            localedir=localedir,
            languages=[lang],
            fallback=True,
        )
    except Exception:
        return gettext.NullTranslations()


def _(msgid: str, default: str | None = None, **kwargs: object) -> str:
    """Translate msgid (user-facing string).

    If translation is missing, fall back to `default` when provided,
    otherwise fall back to `msgid`.
    """
    lang = get_thread_lang() or detect_lang()
    tr = _get_translation(lang)
    try:
        text = tr.gettext(msgid)
    except Exception:
        text = msgid

    if text == msgid and default is not None:
        text = default

    if kwargs:
        if "%(" in text:
            try:
                return text % kwargs
            except Exception:
                pass
        try:
            return text.format(**kwargs)
        except Exception:
            try:
                return text % kwargs
            except Exception:
                pass

    return text


def ngettext(singular: str, plural: str, n: int) -> str:
    """Plural-aware translation."""

    lang = detect_lang()
    tr = _get_translation(lang)
    try:
        return tr.ngettext(singular, plural, n)
    except Exception:
        return singular if n == 1 else plural
