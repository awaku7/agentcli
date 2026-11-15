"""Word extraction for session-log search indexing.

The session store's FTS tokenizer cannot split Japanese, Chinese,
Thai or Korean text into words, so those scripts fall back to raw
substring matching and miss inflected forms (a note saved as 決めた is
not found by 決める). This module extracts content words (nouns and
verbs, in base form) with the same optional analyzers the tool
catalog uses — Janome for Japanese, jieba for Chinese, pythainlp for
Thai, Kiwi (kiwipiepy) for Korean — so the store can index them when
a message is written and match them when a query arrives.

Two rules keep the write path safe:

- Analyzers are used only when already importable here. This module
  never installs packages (the tool catalog's lazy installer is what
  brings Janome and friends in); indexing defers to a later backfill
  when an analyzer is missing.
- Extraction never raises. A failure simply yields no terms.

Opt out with ``UAGENT_SESSION_TERMS=0``.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Callable

from ..env_utils import env_get

_MAX_INDEX_CHARS = 8000
_MAX_QUERY_CHARS = 1000
_MAX_TERMS = 200
_MAX_QUERY_TERMS = 12

_JAPANESE_SCRIPT_RE = re.compile(r"[\u3040-\u30ff]")
_KOREAN_SCRIPT_RE = re.compile(r"[\uac00-\ud7a3\u1100-\u11ff]")
_THAI_SCRIPT_RE = re.compile(r"[\u0e00-\u0e7f]")
_CJK_SCRIPT_RE = re.compile(r"[\u4e00-\u9fff]")

_lock = threading.Lock()
_tokenizers: dict[str, Any] = {}
# script -> monotonic time of the last failed load attempt. Failures
# are retried after a cooldown instead of cached forever: the tool
# catalog's lazy installer can bring an analyzer in mid-process, and
# indexing should pick it up without a restart.
_unavailable: dict[str, float] = {}
_LOAD_RETRY_SECONDS = 60.0


def terms_enabled() -> bool:
    value = (env_get("UAGENT_SESSION_TERMS") or "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def detect_script(text: str) -> str | None:
    """Return the analyzer script a text needs, or None.

    Kana marks Japanese and Hangul marks Korean unambiguously. Text
    with only CJK ideographs is attributed by the UI locale, the same
    tie-break the tool catalog uses.
    """
    if _JAPANESE_SCRIPT_RE.search(text):
        return "ja"
    if _KOREAN_SCRIPT_RE.search(text):
        return "ko"
    if _THAI_SCRIPT_RE.search(text):
        return "th"
    if _CJK_SCRIPT_RE.search(text):
        try:
            from ..i18n import get_locale

            locale = str(get_locale() or "").lower()
        except Exception:
            locale = ""
        return "ja" if locale.startswith("ja") else "zh"
    return None


def _load_tokenizer(script: str) -> Any | None:
    """Return the cached tokenizer for ``script`` if importable."""
    with _lock:
        if script in _tokenizers:
            return _tokenizers[script]
        failed_at = _unavailable.get(script)
        if failed_at is not None and time.monotonic() - failed_at < _LOAD_RETRY_SECONDS:
            return None
    tokenizer: Any = None
    try:
        if script == "ja":
            from janome.tokenizer import Tokenizer

            tokenizer = Tokenizer()
        elif script == "zh":
            import jieba

            tokenizer = jieba
        elif script == "th":
            from pythainlp import word_tokenize

            tokenizer = word_tokenize
        elif script == "ko":
            from kiwipiepy import Kiwi

            tokenizer = Kiwi()
    except Exception:
        tokenizer = None
    with _lock:
        if tokenizer is None:
            _unavailable[script] = time.monotonic()
        else:
            _tokenizers[script] = tokenizer
            _unavailable.pop(script, None)
    return tokenizer


def _janome_terms(tokenizer: Any, text: str) -> list[str]:
    out: list[str] = []
    for token in tokenizer.tokenize(text):
        pos = str(getattr(token, "part_of_speech", "") or "").split(",", 1)[0]
        if pos not in {"名詞", "動詞", "Noun", "Verb"}:
            continue
        term = str(getattr(token, "base_form", "") or "").strip()
        if not term or term == "*":
            term = str(getattr(token, "surface", "") or "").strip()
        if term:
            out.append(term.lower())
    return out


def _jieba_terms(tokenizer: Any, text: str) -> list[str]:
    out: list[str] = []
    for token in tokenizer.lcut(text):
        term = str(token or "").strip().lower()
        if term and any(char.isalnum() for char in term):
            out.append(term)
    return out


def _thai_terms(tokenizer: Any, text: str) -> list[str]:
    tokens = [str(token or "").strip() for token in tokenizer(text, engine="newmm")]
    tokens = [token for token in tokens if token and not token.isspace()]
    if not tokens:
        return []
    try:
        from pythainlp import pos_tag

        tags = pos_tag(tokens, engine="perceptron", corpus="orchid")
    except Exception:
        tags = [(token, "") for token in tokens]
    out: list[str] = []
    for token, pos in tags:
        term = token.strip().lower()
        if term and (not pos or str(pos).startswith(("N", "V"))):
            out.append(term)
    return out


def _kiwi_terms(tokenizer: Any, text: str) -> list[str]:
    out: list[str] = []
    for token in tokenizer.tokenize(text):
        form = str(getattr(token, "form", "") or "").strip()
        tag = str(getattr(token, "tag", "") or "")
        if not form:
            continue
        if tag.startswith("N"):
            out.append(form)
        elif tag.startswith(("VV", "VA")):
            base = str(getattr(token, "base_form", "") or "").strip()
            out.append(base if base and base != form else form + "다")
    return out


_EXTRACTORS: dict[str, Callable[[Any, str], list[str]]] = {
    "ja": _janome_terms,
    "zh": _jieba_terms,
    "th": _thai_terms,
    "ko": _kiwi_terms,
}


def _extract(script: str, text: str) -> list[str] | None:
    tokenizer = _load_tokenizer(script)
    if tokenizer is None:
        return None
    try:
        raw = _EXTRACTORS[script](tokenizer, text)
    except Exception:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for term in raw:
        term = term.strip()
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
            if len(terms) >= _MAX_TERMS:
                break
    return terms


def index_terms(text: str) -> list[str] | None:
    """Content words to index for a stored message.

    Returns None when the text needs an analyzer that is not
    available yet, so the caller leaves the message unindexed for a
    later backfill instead of recording it as term-less. An empty
    list means the message was processed and has no index terms.
    """
    if not text:
        return []
    script = detect_script(text[:_MAX_INDEX_CHARS])
    if script is None:
        return []
    return _extract(script, text[:_MAX_INDEX_CHARS])


def query_terms(query: str) -> list[str]:
    """Content words to match for a search query (never None)."""
    if not query:
        return []
    script = detect_script(query[:_MAX_QUERY_CHARS])
    if script is None:
        return []
    terms = _extract(script, query[:_MAX_QUERY_CHARS])
    if not terms:
        return []
    return terms[:_MAX_QUERY_TERMS]
