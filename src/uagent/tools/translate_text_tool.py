from __future__ import annotations

import json
import ssl
import time
import urllib.request
import urllib.parse
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

LAZY_LOAD = True
MAX_TEXT_LENGTH = 10000
BUSY_LABEL = True

# Locale code mapping: project format (zh_CN) -> Google Translate format (zh-CN)
_LOCALE_TO_GOOGLE: dict[str, str] = {
    "ja": "ja",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "ko": "ko",
    "de": "de",
    "it": "it",
    "ru": "ru",
    "pt_BR": "pt",
    "pt": "pt",
    "id": "id",
    "vi": "vi",
    "pl": "pl",
    "hi": "hi",
    "ar": "ar",
    "sv": "sv",
    "sw": "sw",
    "nb": "nb",
    "nl": "nl",
    "fi": "fi",
    "cs": "cs",
    "uk": "uk",
    "tr": "tr",
    "th": "th",
    "zh_CN": "zh-CN",
    "zh_TW": "zh-TW",
    "bn": "bn",
    "fa": "fa",
    "mn": "mn",
    "mr": "mr",
    "el": "el",
    "he": "he",
    "hu": "hu",
    "ro": "ro",
}


# Reverse mapping: Google format -> project format
_GOOGLE_TO_LOCALE: dict[str, str] = {v: k for k, v in _LOCALE_TO_GOOGLE.items()}

# SSL context (Google Translate cert issues)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Last request timestamp for rate limiting
_LAST_REQUEST_TIME: float = 0


def _translate(
    text: str, target_lang: str, source_lang: str | None = None
) -> tuple[str, str | None]:
    """Call Google Translate's non-public API.

    Returns (translated_text, detected_source_lang_or_None).
    """
    global _LAST_REQUEST_TIME
    # Rate limiting: at least 0.5s between requests
    now = time.time()
    since_last = now - _LAST_REQUEST_TIME
    if since_last < 0.5:
        time.sleep(0.5 - since_last)

    params: dict[str, str] = {
        "client": "gtx",
        "sl": source_lang if source_lang else "auto",
        "tl": target_lang,
        "dt": "t",
        "q": text,
    }
    url = (
        "https://translate.googleapis.com/translate_a/single?"
        + urllib.parse.urlencode(params)
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parts: list[str] = []
            for segment in data[0]:
                if segment[0]:
                    parts.append(segment[0])
            translated = "".join(parts)
            # data[2] contains detected source language (e.g. "en") when source is auto
            detected_raw = (
                data[2] if len(data) > 2 and isinstance(data[2], str) else None
            )
            detected = (
                _GOOGLE_TO_LOCALE.get(detected_raw, detected_raw)
                if detected_raw
                else None
            )
            _LAST_REQUEST_TIME = time.time()
            return translated, detected
    except Exception as e:
        raise RuntimeError(f"Translation request failed: {e}")


TOOL_SPEC: dict[str, Any] = {
    "tool_level": 1,
    "tool_genre": "devel",
    "type": "function",
    "x_parallel_safe": True,
    "function": {
        "name": "translate_text",
        "description": _(
            "tool.description",
            default="Translate text using Google Translate. Supports 30+ languages. Max input length: 10000 characters.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=["translate", "translation", "google translate", "language"],
        ),
        "x_search_terms_en": [
            "translate",
            "translation",
            "google translate",
            "language",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": _(
                        "param.text.description",
                        default="Text to translate (max 10000 characters).",
                    ),
                },
                "target_lang": {
                    "type": "string",
                    "description": _(
                        "param.target_lang.description",
                        default="Target language code (e.g. ja, en, zh_CN, pt_BR, fr, de, es, ko).",
                    ),
                },
                "source_lang": {
                    "type": "string",
                    "description": _(
                        "param.source_lang.description",
                        default="Source language code. Auto-detected if omitted.",
                    ),
                },
            },
            "required": ["text", "target_lang"],
        },
    },
}


def run_tool(args: dict[str, Any]) -> str:
    text = str(args.get("text") or "").strip()
    target_lang = str(args.get("target_lang") or "").strip()
    source_lang = str(args.get("source_lang") or "").strip() or None

    if not text:
        return json.dumps({"error": "text is required"}, ensure_ascii=False)
    if len(text) > MAX_TEXT_LENGTH:
        return json.dumps(
            {"error": f"Text too long: {len(text)} characters (max {MAX_TEXT_LENGTH})"},
            ensure_ascii=False,
        )
    if not target_lang:
        return json.dumps({"error": "target_lang is required"}, ensure_ascii=False)

    # Normalise locale code: lowercase and map to Google format
    target_norm = target_lang.lower().replace("-", "_")
    google_target = _LOCALE_TO_GOOGLE.get(target_norm)
    if google_target is None:
        return json.dumps(
            {"error": f"Unsupported target language: {target_lang}"},
            ensure_ascii=False,
        )

    google_source: str | None = None
    if source_lang:
        source_norm = source_lang.lower().replace("-", "_")
        google_source = _LOCALE_TO_GOOGLE.get(source_norm)
        if google_source is None:
            return json.dumps(
                {"error": f"Unsupported source language: {source_lang}"},
                ensure_ascii=False,
            )

    try:
        translated, detected = _translate(text, google_target, google_source)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    result: dict[str, Any] = {"translated": translated}
    if detected:
        result["detected_source_lang"] = detected

    return json.dumps(result, ensure_ascii=False)
