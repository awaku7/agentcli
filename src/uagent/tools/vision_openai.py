# -*- coding: utf-8 -*-
"""vision_openai.py

Image analysis backend for OpenAI/Azure OpenAI (Chat Completions).

This module is used by tools/analyze_image_tool.py when UAGENT_RESPONSES is OFF.

Notes:
- Uses OpenAI SDK (OpenAI/AzureOpenAI).
- Sends the image as a data URL (base64) in the standard OpenAI multimodal format.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from ..env_utils import env_get


def _image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    p = Path(str(path))
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"image file not found: {path}")

    size = p.stat().st_size
    if size > int(max_bytes):
        raise ValueError(f"image file too large: {size} bytes (limit={max_bytes})")

    mt, _ = mimetypes.guess_type(str(p))
    mime_type = mt or "application/octet-stream"

    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def _env_first(keys: list[str], *, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    return default


def _img_env(provider: str, mode: str, name: str, *, default: str = "") -> str:
    """Resolve image env vars with fallback to main provider env vars.

    Example (provider=openai, mode=analysis, name=depname):
      - UAGENT_OPENAI_IMG_ANALYSIS_DEPNAME
      - UAGENT_OPENAI_DEPNAME
    """

    p = provider.strip().upper()
    m = mode.strip().upper()
    n = name.strip().upper()
    return _env_first(
        [
            f"UAGENT_IMG_{m}_{n}",
            f"UAGENT_{p}_IMG_{m}_{n}",
            f"UAGENT_{p}_{n}",
        ],
        default=default,
    )


def analyze_image_openai(
    *,
    provider: str,
    image_path: str,
    prompt: str | None,
) -> str:
    """Analyze an image using OpenAI/Azure OpenAI Chat Completions."""

    provider_l = (provider or "").strip().lower()
    if provider_l not in ("openai", "azure"):
        raise RuntimeError(f"Unsupported provider for analyze_image (chat): {provider!r}")

    try:
        from openai import AzureOpenAI, OpenAI
    except Exception as e:
        raise RuntimeError(f"Failed to import openai package: {e!r}")

    text = (prompt or "").strip() or "Please describe this image in detail."
    data_url = _image_file_to_data_url(image_path)

    # Provider-specific client + model
    if provider_l == "azure":
        base_url = _img_env("azure", "analysis", "base_url") or _env_first([
            "UAGENT_AZURE_BASE_URL",
        ])
        api_key = _img_env("azure", "analysis", "api_key") or _env_first([
            "UAGENT_AZURE_API_KEY",
        ])
        api_version = _img_env("azure", "analysis", "api_version") or _env_first([
            "UAGENT_AZURE_API_VERSION",
        ])
        model = _img_env("azure", "analysis", "depname") or _env_first([
            "UAGENT_AZURE_DEPNAME",
        ])
        if not (base_url and api_key and api_version and model):
            raise RuntimeError(
                "Missing required env vars for azure image analysis. "
                "Need base_url/api_key/api_version/model (UAGENT_AZURE_* or UAGENT_AZURE_IMG_ANALYSIS_*)."
            )
        client = AzureOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
        )
    else:
        api_key = _img_env("openai", "analysis", "api_key") or _env_first([
            "UAGENT_OPENAI_API_KEY",
        ])
        base_url = (
            _img_env("openai", "analysis", "base_url")
            or env_get("UAGENT_OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        model = _img_env("openai", "analysis", "depname") or _env_first([
            "UAGENT_OPENAI_DEPNAME",
        ])
        if not (api_key and model):
            raise RuntimeError(
                "Missing required env vars for openai image analysis. "
                "Need api_key/model (UAGENT_OPENAI_* or UAGENT_OPENAI_IMG_ANALYSIS_*)."
            )
        client = OpenAI(api_key=api_key, base_url=base_url)

    # Chat Completions multimodal
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

    out = None
    try:
        out = resp.choices[0].message.content
    except Exception:
        out = None

    return (out or "").strip() or "[WARN] empty response"
