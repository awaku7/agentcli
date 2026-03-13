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

    if len(parts) >= 2:
        # script or region
        if len(parts[1]) == 4:
            script = parts[1].title()  # Hans/Hant
        else:
            region = parts[1].upper()
    if len(parts) >= 3:
        # region if script present
        if script and not region:
            region = parts[2].upper()

    # Japanese
    if lang.startswith("ja"):
        return "ja" if "ja" in supported else "en"

    # English
    if lang.startswith("en"):
        return "en"

    # Chinese: map Hans/Hant to CN/TW when available
    if lang.startswith("zh"):
        # explicit region
        if region in {"CN", "SG"}:
            return (
                "zh_CN"
                if "zh_CN" in supported
                else ("zh_TW" if "zh_TW" in supported else "en")
            )
        if region in {"TW", "HK", "MO"}:
            return (
                "zh_TW"
                if "zh_TW" in supported
                else ("zh_CN" if "zh_CN" in supported else "en")
            )

        # script hint
        if script == "Hans":
            return (
                "zh_CN"
                if "zh_CN" in supported
                else ("zh_TW" if "zh_TW" in supported else "en")
            )
        if script == "Hant":
            return (
                "zh_TW"
                if "zh_TW" in supported
                else ("zh_CN" if "zh_CN" in supported else "en")
            )

        # plain 'zh'
        if "zh_CN" in supported:
            return "zh_CN"
        if "zh_TW" in supported:
            return "zh_TW"
        return "en"

    # General case: if we have exact lang catalog, use it.
    if lang and lang in supported:
        return lang

    return "en"


def detect_lang() -> str:
    """Detect runtime language.

    Returns:
      'ja' or 'en' (current policy).
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


def _(msgid: str) -> str:
    """Translate msgid (user-facing string)."""
    lang = get_thread_lang() or detect_lang()
    tr = _get_translation(lang)
    try:
        return tr.gettext(msgid)
    except Exception:
        return msgid


def ngettext(singular: str, plural: str, n: int) -> str:
    """Plural-aware translation."""

    lang = detect_lang()
    tr = _get_translation(lang)
    try:
        return tr.ngettext(singular, plural, n)
    except Exception:
        return singular if n == 1 else plural
