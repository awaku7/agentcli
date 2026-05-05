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
    - openai / azure / openrouter / openai_compat -> OpenAI-compatible HTTP providers
    - gemini -> google-genai
    - claude -> anthropic
- UAGENT_TRANSLATE_TO_LLM: e.g. 'en'
- UAGENT_TRANSLATE_FROM_LLM: e.g. 'ja'

Translation settings:
- UAGENT_TRANSLATE_DEPNAME: model name for translation (optional; falls back per provider)
- UAGENT_TRANSLATE_API_KEY: optional (falls back per provider)
- UAGENT_TRANSLATE_BASE_URL: optional (OpenAI-compatible providers only)

Notes:
- Gemini / Claude are implemented with lazy imports and best-effort fallbacks.
- If a provider is unavailable or translation fails, the original text is returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .env_utils import env_get

# OpenAI-compatible providers
try:
    from openai import OpenAI  # type: ignore
except Exception:  # openai 未インストール時など
    OpenAI = None  # type: ignore[assignment]

# Google Gemini (google-genai)
try:
    from google import genai
    from google.genai import types as gemini_types
except Exception:  # google-genai 未インストール時など
    genai = None  # type: ignore[assignment]
    gemini_types = None  # type: ignore[assignment]

# Anthropic Claude
try:
    from anthropic import Anthropic
except Exception:  # anthropic 未インストール時など
    Anthropic = None  # type: ignore[assignment]


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
    letters = sum(1 for ch in sample if "a" <= ch.lower() <= "z")
    return letters >= 10


def _env_first(*names: str) -> str:
    for name in names:
        v = (env_get(name) or "").strip()
        if v:
            return v
    return ""


@dataclass
class TranslateConfig:
    provider: str
    to_llm: str
    from_llm: str
    depname: str
    api_key: str
    base_url: str


def load_translate_config() -> Optional[TranslateConfig]:
    provider = (env_get("UAGENT_TRANSLATE_PROVIDER") or "").strip().lower()
    if not provider:
        return None

    to_llm = _norm_lang(env_get("UAGENT_TRANSLATE_TO_LLM") or "")
    from_llm = _norm_lang(env_get("UAGENT_TRANSLATE_FROM_LLM") or "")

    if provider in ("openai", "openai_compat"):
        depname = _env_first("UAGENT_TRANSLATE_DEPNAME", "UAGENT_OPENAI_DEPNAME")
        api_key = _env_first(
            "UAGENT_TRANSLATE_API_KEY", "UAGENT_OPENAI_API_KEY", "UAGENT_API_KEY"
        )
        base_url = _env_first(
            "UAGENT_TRANSLATE_BASE_URL", "UAGENT_OPENAI_BASE_URL", "UAGENT_BASE_URL"
        )
    elif provider == "azure":
        depname = _env_first("UAGENT_TRANSLATE_DEPNAME", "UAGENT_AZURE_DEPNAME")
        api_key = _env_first(
            "UAGENT_TRANSLATE_API_KEY", "UAGENT_AZURE_API_KEY", "UAGENT_API_KEY"
        )
        base_url = _env_first(
            "UAGENT_TRANSLATE_BASE_URL", "UAGENT_AZURE_BASE_URL", "UAGENT_BASE_URL"
        )
    elif provider == "openrouter":
        depname = _env_first(
            "UAGENT_TRANSLATE_DEPNAME", "UAGENT_OPENROUTER_DEPNAME"
        )
        api_key = _env_first(
            "UAGENT_TRANSLATE_API_KEY",
            "UAGENT_OPENROUTER_API_KEY",
            "UAGENT_API_KEY",
        )
        base_url = _env_first(
            "UAGENT_TRANSLATE_BASE_URL",
            "UAGENT_OPENROUTER_BASE_URL",
            "UAGENT_BASE_URL",
        )
    elif provider == "gemini":
        depname = _env_first("UAGENT_TRANSLATE_DEPNAME", "UAGENT_GEMINI_DEPNAME")
        api_key = _env_first(
            "UAGENT_TRANSLATE_API_KEY", "UAGENT_GEMINI_API_KEY", "UAGENT_API_KEY"
        )
        base_url = _env_first("UAGENT_TRANSLATE_BASE_URL", "UAGENT_BASE_URL")
    elif provider == "claude":
        depname = _env_first("UAGENT_TRANSLATE_DEPNAME", "UAGENT_CLAUDE_DEPNAME")
        api_key = _env_first(
            "UAGENT_TRANSLATE_API_KEY", "UAGENT_CLAUDE_API_KEY", "UAGENT_API_KEY"
        )
        base_url = _env_first("UAGENT_TRANSLATE_BASE_URL", "UAGENT_BASE_URL")
    else:
        depname = _env_first("UAGENT_TRANSLATE_DEPNAME")
        api_key = _env_first("UAGENT_TRANSLATE_API_KEY", "UAGENT_API_KEY")
        base_url = _env_first("UAGENT_TRANSLATE_BASE_URL", "UAGENT_BASE_URL")

    return TranslateConfig(
        provider=provider,
        to_llm=to_llm,
        from_llm=from_llm,
        depname=depname,
        api_key=api_key,
        base_url=base_url,
    )


def _translation_prompts(src_lang: str, dst_lang: str, text: str) -> Tuple[str, str]:
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
    return system, user


def _translate_openai_compat(
    text: str, *, src_lang: str, dst_lang: str, cfg: TranslateConfig
) -> Tuple[str, str]:
    if OpenAI is None:
        return text, "openai package is not installed."
    if not cfg.depname:
        return text, "UAGENT_TRANSLATE_DEPNAME is not set (skip translation)."

    try:
        kwargs: dict[str, Any] = {}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url

        client = OpenAI(**kwargs)
        system, user = _translation_prompts(src_lang, dst_lang, text)

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


def _extract_gemini_text(resp: Any) -> str:
    out = getattr(resp, "text", None)
    if isinstance(out, str) and out.strip():
        return out.strip()

    parts_out: list[str] = []
    try:
        candidates = getattr(resp, "candidates", None)
        if candidates:
            candidate = candidates[0]
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None)
            if parts:
                for part in parts:
                    t = getattr(part, "text", None)
                    if isinstance(t, str) and t.strip():
                        parts_out.append(t)
    except Exception:
        pass
    return "".join(parts_out).strip()


def _translate_gemini(
    text: str, *, src_lang: str, dst_lang: str, cfg: TranslateConfig
) -> Tuple[str, str]:
    if genai is None:
        return text, "google-genai package is not installed."
    if not cfg.depname:
        return text, "UAGENT_TRANSLATE_DEPNAME is not set (skip translation)."

    try:
        kwargs: dict[str, Any] = {}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        client = genai.Client(**kwargs)

        system, user = _translation_prompts(src_lang, dst_lang, text)
        prompt = f"{system}\n\n{user}"

        gen_config: Any = None
        if gemini_types is not None:
            try:
                gen_config = gemini_types.GenerateContentConfig(temperature=0)
            except Exception:
                gen_config = None

        try:
            if gen_config is not None:
                resp = client.models.generate_content(
                    model=cfg.depname,
                    contents=prompt,
                    config=gen_config,
                )
            else:
                resp = client.models.generate_content(
                    model=cfg.depname,
                    contents=prompt,
                )
        except TypeError:
            if gen_config is not None:
                resp = client.models.generate_content(
                    model=cfg.depname,
                    contents=[{"role": "user", "parts": [{"text": prompt}]}],
                    config=gen_config,
                )
            else:
                resp = client.models.generate_content(
                    model=cfg.depname,
                    contents=[{"role": "user", "parts": [{"text": prompt}]}],
                )

        out = _extract_gemini_text(resp)
        if not out:
            return text, "translation model returned empty text"
        return out, ""
    except Exception as e:
        return text, f"gemini translate error: {type(e).__name__}: {e}"


def _translate_claude(
    text: str, *, src_lang: str, dst_lang: str, cfg: TranslateConfig
) -> Tuple[str, str]:
    if Anthropic is None:
        return text, "anthropic package is not installed."
    if not cfg.depname:
        return text, "UAGENT_TRANSLATE_DEPNAME is not set (skip translation)."

    try:
        kwargs: dict[str, Any] = {}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        client = Anthropic(**kwargs)

        system, user = _translation_prompts(src_lang, dst_lang, text)
        response = client.messages.create(
            model=cfg.depname,
            max_tokens=4096,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        parts_out: list[str] = []
        content = getattr(response, "content", None)
        if content:
            for block in content:
                btype = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                if btype != "text":
                    continue
                txt = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
                if isinstance(txt, str) and txt.strip():
                    parts_out.append(txt)

        out = "".join(parts_out).strip()
        if not out:
            return text, "translation model returned empty text"
        return out, ""
    except Exception as e:
        return text, f"claude translate error: {type(e).__name__}: {e}"


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
        return text, ""

    if dst_lang.split("_", 1)[0] == "en" and _looks_english(text):
        return text, ""

    if cfg.provider in ("openai", "azure", "openrouter", "openai_compat"):
        return _translate_openai_compat(
            text, src_lang=src_lang, dst_lang=dst_lang, cfg=cfg
        )
    if cfg.provider == "gemini":
        return _translate_gemini(text, src_lang=src_lang, dst_lang=dst_lang, cfg=cfg)
    if cfg.provider == "claude":
        return _translate_claude(text, src_lang=src_lang, dst_lang=dst_lang, cfg=cfg)

    return (
        text,
        f"translate provider not implemented: {cfg.provider!r} (set to an OpenAI-compatible provider, gemini, or claude)",
    )
