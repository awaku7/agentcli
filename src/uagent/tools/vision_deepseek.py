# -*- coding: utf-8 -*-
"""vision_deepseek.py - Image analysis via DeepSeek API (OpenAI-compatible)."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            _("vision.img_not_found", default=f"Image not found: {path}")
        )
    size = p.stat().st_size
    if size > max_bytes:
        raise ValueError(
            _(
                "vision.img_too_large",
                default=f"Image too large: {size} bytes (max={max_bytes})",
            )
        )
    mime, _enc = mimetypes.guess_type(str(p))
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return _("vision.data_uri", default=f"data:{mime or 'image/jpeg'};base64,{b64}")


def _get_deepseek_client():
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            _("err.import_openai", default="Failed to import openai package.")
        )

    api_key = get_provider_api_key("deepseek") or get_provider_api_key("openai")
    base_url = env_get("UAGENT_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    if not api_key:
        raise RuntimeError(
            _(
                "err.missing_env",
                default="Missing UAGENT_DEEPSEEK_API_KEY (or UAGENT_OPENAI_API_KEY).",
            )
        )
    return OpenAI(api_key=api_key, base_url=base_url)


def analyze_image_deepseek(*, image_path: str, prompt: str | None) -> str:
    client = _get_deepseek_client()
    model = (
        env_get("UAGENT_DEEPSEEK_DEPNAME", "deepseek-v4-flash") or "deepseek-v4-flash"
    )
    text = (prompt or "").strip() or "Please describe this image in detail."
    data_url = _image_file_to_data_url(image_path)

    try:
        try:
            from uagent.llmcapa_util import (
                check_vision_support,
                vision_completion_max_tokens,
            )

            vision_err = check_vision_support(model, "deepseek")
            if vision_err:
                return json.dumps(
                    {"ok": False, "error": vision_err},
                    ensure_ascii=False,
                )
            max_tokens = vision_completion_max_tokens(model, "deepseek", default=1024)
        except Exception:
            max_tokens = 1024

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return (content or "").strip() or _(
            "warn.empty", default="[WARN] empty response"
        )
    except Exception as e:
        err = str(e)
        if "image_url" in err or "image" in err.lower():
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        "The configured DeepSeek endpoint does not support image input. "
                        "To use DeepSeek vision, set UAGENT_DEEPSEEK_BASE_URL to a vision-capable endpoint "
                        "(e.g., a provider that supports vision models) and UAGENT_DEEPSEEK_DEPNAME to the model name. "
                        "Current models available: deepseek-v4-flash, deepseek-v4-pro (text-only)."
                    ),
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"ok": False, "error": f"DeepSeek vision call failed: {err[:200]}"},
            ensure_ascii=False,
        )
