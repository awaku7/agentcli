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
from functools import lru_cache
from typing import Optional

from pathlib import Path


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


def _normalize_lang_tag(tag: Optional[str]) -> str:
    """Normalize various locale tags into a simple language code.

    Examples:
      - 'ja_JP', 'ja-JP', 'ja_JP.UTF-8' -> 'ja'
      - 'en_US', 'en-US' -> 'en'

    Plan A:
      - if startswith('ja') -> 'ja'
      - else -> 'en'
    """

    if not tag:
        return "en"

    t = str(tag).strip()
    if not t:
        return "en"

    # Drop encoding ('.UTF-8') and modifiers ('@...')
    t = t.split(".", 1)[0].split("@", 1)[0]

    # Normalize delimiter
    t = t.replace("-", "_")

    # Take language part
    lang = t.split("_", 1)[0].lower()

    if lang.startswith("ja"):
        return "ja"
    return "en"


def detect_lang() -> str:
    """Detect runtime language.

    Returns:
      'ja' or 'en' (current policy).
    """

    # 1) explicit override
    v = (os.environ.get("UAGENT_LANG") or "").strip()
    if v:
        return _normalize_lang_tag(v)

    # 2) common env vars
    for k in ("LC_ALL", "LANG"):
        vv = (os.environ.get(k) or "").strip()
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

    lang = detect_lang()
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
