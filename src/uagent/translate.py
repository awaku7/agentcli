"""uagent.translate

Lightweight, optional translation helpers.

Design goals:
- Off by default: if env vars are not set, do nothing.
- Stateless per call (no session/history).
- Safe failure: on errors, return original text and a diagnostic string.

Env vars
--------
Enable translation by setting these:
- UAGENT_TRANSLATE_PROVIDER:
    - 'argos' -> local Argos Translate
    - anything else -> treated as UAGENT_PROVIDER-compatible; currently only
      OpenAI-compatible providers are supported here (azure/openai/openrouter/etc.)
- UAGENT_TRANSLATE_TO_LLM: e.g. 'en'
- UAGENT_TRANSLATE_FROM_LLM: e.g. 'ja'

OpenAI-compatible translation settings:
- UAGENT_TRANSLATE_DEPNAME: model name for translation (required)
- UAGENT_TRANSLATE_API_KEY: optional (falls back to UAGENT_API_KEY)
- UAGENT_TRANSLATE_BASE_URL: optional (falls back to UAGENT_BASE_URL)

Notes:
- We intentionally do not implement Gemini/Claude translation here yet.
  If UAGENT_TRANSLATE_PROVIDER is set to those values, translation is skipped
  with a diagnostic.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

_LANG_RE = re.compile(r"^[a-zA-Z]{2,3}([_-][a-zA-Z0-9]{2,8})*$")


def _norm_lang(tag: str) -> str:
    t = (tag or "").strip().lower().replace("-", "_")
    if not t:
        return ""
    if not _LANG_RE.match(t):
        return ""
    return t


def _looks_english(text: str) -> bool:
    # Conservative heuristic: if mostly ASCII and contains common English letters.
    if not text:
        return True
    sample = text[:4000]
    ascii_count = sum(1 for ch in sample if ord(ch) < 128)
    ratio = ascii_count / max(1, len(sample))
    if ratio < 0.92:
        return False
    # If it contains a decent amount of letters (avoid pure code/paths)
    letters = sum(1 for ch in sample if "a" <= ch.lower() <= "z")
    return letters >= 10


@dataclass
class TranslateConfig:
    provider: str
    to_llm: str
    from_llm: str
    depname: str
    api_key: str
    base_url: str


def load_translate_config() -> Optional[TranslateConfig]:
    provider = (os.environ.get("UAGENT_TRANSLATE_PROVIDER") or "").strip().lower()
    if not provider:
        return None

    to_llm = _norm_lang(os.environ.get("UAGENT_TRANSLATE_TO_LLM") or "")
    from_llm = _norm_lang(os.environ.get("UAGENT_TRANSLATE_FROM_LLM") or "")

    depname = (os.environ.get("UAGENT_TRANSLATE_DEPNAME") or "").strip()
    api_key = (
        os.environ.get("UAGENT_TRANSLATE_API_KEY")
        or os.environ.get("UAGENT_API_KEY")
        or ""
    ).strip()
    base_url = (
        os.environ.get("UAGENT_TRANSLATE_BASE_URL")
        or os.environ.get("UAGENT_BASE_URL")
        or ""
    ).strip()

    return TranslateConfig(
        provider=provider,
        to_llm=to_llm,
        from_llm=from_llm,
        depname=depname,
        api_key=api_key,
        base_url=base_url,
    )


def _translate_openai_compat(
    text: str, *, src_lang: str, dst_lang: str, cfg: TranslateConfig
) -> Tuple[str, str]:
    if not cfg.depname:
        return text, "UAGENT_TRANSLATE_DEPNAME is not set (skip translation)."

    try:
        # Lazy import so base install does not require openai.
        from openai import OpenAI  # type: ignore

        kwargs: dict[str, Any] = {}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url

        client = OpenAI(**kwargs)

        system = (
            "You are a translation engine. "
            "Translate the user's text faithfully. "
            "Do not add explanations. "
            "Preserve code blocks, inline code, JSON, file paths, and URLs verbatim."
        )
        user = (
            f"Translate from {src_lang or 'auto'} to {dst_lang}.\n\n"
            "Return only the translated text.\n\n"
            f"TEXT:\n{text}"
        )

        resp = client.chat.completions.create(
            model=cfg.depname,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        out = (resp.choices[0].message.content or "").strip()
        if not out:
            return text, "translation model returned empty text"
        return out, ""
    except Exception as e:
        return text, f"openai_compat translate error: {type(e).__name__}: {e}"


def _translate_argos(text: str, *, src_lang: str, dst_lang: str) -> Tuple[str, str]:
    try:
        # Argos Translate is optional.
        import argostranslate.translate as argos_translate  # type: ignore

        out = argos_translate.translate(text, src_lang or "", dst_lang)
        if not isinstance(out, str) or not out.strip():
            return text, "argos returned empty text"
        return out, ""
    except Exception as e:
        return text, f"argos translate error: {type(e).__name__}: {e}"


def translate_text(
    text: str,
    *,
    direction: str,
    src_lang: str,
    cfg: Optional[TranslateConfig] = None,
) -> Tuple[str, str]:
    """Translate text in one direction.

    direction:
      - 'to_llm': translate into cfg.to_llm
      - 'from_llm': translate into cfg.from_llm

    Returns: (translated_text, diagnostic_message)
    - diagnostic_message is '' on success or when translation is skipped.
    """

    cfg = cfg or load_translate_config()
    if cfg is None:
        return text, ""

    if not isinstance(text, str) or not text.strip():
        return text, ""

    if direction == "to_llm":
        dst_lang = cfg.to_llm
    elif direction == "from_llm":
        dst_lang = cfg.from_llm
    else:
        return text, f"invalid translate direction: {direction!r}"

    if not dst_lang:
        # Not configured -> no translation.
        return text, ""

    # If target is English and the text already looks English, skip.
    if dst_lang.split("_", 1)[0] == "en" and _looks_english(text):
        return text, ""

    if cfg.provider == "argos":
        return _translate_argos(text, src_lang=src_lang, dst_lang=dst_lang)

    # Provider string is "UAGENT_PROVIDER compatible".
    # Currently, we only implement OpenAI-compatible HTTP providers.
    if cfg.provider in ("openai", "azure", "openrouter", "openai_compat"):
        return _translate_openai_compat(
            text, src_lang=src_lang, dst_lang=dst_lang, cfg=cfg
        )

    return (
        text,
        f"translate provider not implemented: {cfg.provider!r} (set to 'argos' or an OpenAI-compatible provider)",
    )
