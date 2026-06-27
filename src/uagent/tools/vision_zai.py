# -*- coding: utf-8 -*-
"""vision_zai.py - Image analysis via Z.AI (Zhipu AI) API using GLM-4.6V.

This module is used by tools/analyze_image_tool.py when the provider is "zai".

Notes:
- Z.AI API endpoint (https://api.z.ai/api/paas/v4/) is OpenAI-compatible,
  so the OpenAI SDK is used for chat completions with image_url content.
- Default vision model is "glm-4.6v". Override with UAGENT_ZAI_IMG_ANALYSIS_DEPNAME
  or UAGENT_IMG_ANALYSIS_DEPNAME.
- The zhipuai SDK is tried first; if unavailable, falls back to the OpenAI SDK.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# Default vision-capable model for Z.AI
_DEFAULT_VISION_MODEL = "glm-4.6v"


def _image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    size = p.stat().st_size
    if size > max_bytes:
        raise ValueError(f"Image too large: {size} bytes (max={max_bytes})")
    mime, _ = mimetypes.guess_type(str(p))
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime or 'image/jpeg'};base64,{b64}"


def _env_first(keys: list[str], *, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    return default


def _get_zai_vision_client_and_model():
    """Build a Z.AI client for vision calls.

    Tries the zhipuai SDK first, then falls back to the OpenAI SDK.
    Returns (client, model_name).
    """
    api_key = _env_first(
        ["UAGENT_ZAI_IMG_ANALYSIS_API_KEY", "UAGENT_ZAI_API_KEY"],
    )
    base_url = _env_first(
        [
            "UAGENT_ZAI_IMG_ANALYSIS_BASE_URL",
            "UAGENT_ZAI_BASE_URL",
        ],
        default="https://api.z.ai/api/paas/v4/",
    )
    model = _env_first(
        [
            "UAGENT_ZAI_IMG_ANALYSIS_DEPNAME",
            "UAGENT_IMG_ANALYSIS_DEPNAME",
        ],
        default=_DEFAULT_VISION_MODEL,
    )

    if not api_key:
        raise RuntimeError(
            _(
                "err.missing_env",
                default=(
                    "Missing UAGENT_ZAI_API_KEY (or UAGENT_ZAI_IMG_ANALYSIS_API_KEY). "
                    "Set it in .env or .env.sec."
                ),
            )
        )

    # Try zhipuai SDK first (preferred for Z.AI)
    try:
        from zhipuai import ZhipuAI

        try:
            client = ZhipuAI(api_key=api_key, base_url=base_url)
        except TypeError:
            client = ZhipuAI(api_key=api_key, base_url=base_url)
        return client, model
    except ImportError:
        pass

    # Fallback to OpenAI SDK (Z.AI endpoint is OpenAI-compatible)
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


def analyze_image_zai(*, image_path: str, prompt: str | None) -> str:
    """Analyze an image using Z.AI (GLM-4.6V) via chat completions."""
    client, model = _get_zai_vision_client_and_model()
    text = (prompt or "").strip() or "Please describe this image in detail."
    data_url = _image_file_to_data_url(image_path)

    try:
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
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return (content or "").strip() or _(
            "warn.empty", default="[WARN] empty response"
        )
    except Exception as e:
        err = str(e)
        if "image" in err.lower() or "vision" in err.lower():
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"The configured Z.AI model ({model}) does not support image input. "
                        "Set UAGENT_ZAI_IMG_ANALYSIS_DEPNAME (or UAGENT_IMG_ANALYSIS_DEPNAME) "
                        "to a vision-capable model such as 'glm-4.6v'."
                    ),
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {"ok": False, "error": f"Z.AI vision call failed: {err[:200]}"},
            ensure_ascii=False,
        )
