# -*- coding: utf-8 -*-
"""vision_zai.py - Image analysis via Z.AI (Zhipu AI) API using GLM-4.6V.

This module is used by tools/analyze_image_tool.py when the provider is "zai".

Notes:
- Z.AI API endpoint (https://api.z.ai/api/paas/v4/) is OpenAI-compatible,
  so the OpenAI SDK is used for chat completions with image_url content.
- Default vision model is "glm-4.6v". Override with UAGENT_ZAI_IMG_ANALYSIS_DEPNAME
  or UAGENT_IMG_ANALYSIS_DEPNAME.
- The zai-sdk (ZaiClient) is used with auto-install; if unavailable,
  falls back to the OpenAI SDK.
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


def _ssl_verify_enabled() -> bool:
    v = (env_get("UAGENT_SSL_VERIFY") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _env_first(keys: list[str], *, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    return default


def _get_zai_vision_client_and_model():
    """Build a Z.AI client for vision calls.

    Uses the zai-sdk (ZaiClient) with auto-install.
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

    # Use zai-sdk (preferred for Z.AI, with auto-install)
    from .._pip_auto import install_with_status as _install_zai_sdk

    if not _install_zai_sdk("zai-sdk", "zai", display_name="zai-sdk"):
        raise RuntimeError(
            _(
                "err.zai_import",
                default="Failed to import zai-sdk. Install with: pip install zai-sdk",
            )
        )
    from zai import ZaiClient

    # Build httpx client with SSL settings
    http_client = None
    try:
        from ..providers import util_providers as providers  # type: ignore

        http_client = providers.make_httpx_client(verify=_ssl_verify_enabled())
    except Exception:
        pass

    try:
        if http_client is not None:
            client = ZaiClient(
                api_key=api_key, base_url=base_url, http_client=http_client
            )
        else:
            client = ZaiClient(api_key=api_key, base_url=base_url)
    except TypeError:
        client = ZaiClient(api_key=api_key, base_url=base_url)
    return client, model


def analyze_image_zai(*, image_path: str, prompt: str | None) -> str:
    """Analyze an image using Z.AI (GLM-4.6V) via chat completions."""
    client, model = _get_zai_vision_client_and_model()
    text = (prompt or "").strip() or "Please describe this image in detail."
    data_url = _image_file_to_data_url(image_path)

    try:
        try:
            from uagent.llmcapa_util import (
                check_vision_support,
                vision_completion_max_tokens,
            )

            vision_err = check_vision_support(model, "zai")
            if vision_err:
                return json.dumps(
                    {"ok": False, "error": vision_err},
                    ensure_ascii=False,
                )
            max_tokens = vision_completion_max_tokens(model, "zai", default=1024)
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
