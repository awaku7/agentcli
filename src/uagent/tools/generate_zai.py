# -*- coding: utf-8 -*-
"""generate_zai.py - Image generation via Z.AI (Zhipu AI) API using GLM-Image.

This module is used by tools/generate_image_tool.py when the provider is "zai".

Notes:
- Uses the zai-sdk (pip install zai-sdk) for image generation.
- Default image generation model is "glm-image".
  Override with UAGENT_ZAI_IMG_GENERATE_DEPNAME or UAGENT_IMG_GENERATE_DEPNAME.
- The API returns an image URL; the caller downloads and saves as PNG.
- API docs: https://docs.z.ai/api-reference/image/generate-image
"""

from __future__ import annotations

from typing import Any

from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# Default image generation model for Z.AI
_DEFAULT_IMAGE_MODEL = "glm-image"

# Default size for GLM-Image (must be multiples of 32, 1024-2048 range)
_DEFAULT_SIZE = "1280x1280"


def _env_first(keys: list[str], *, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    return default


def _ssl_verify_enabled() -> bool:
    v = (env_get("UAGENT_SSL_VERIFY") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _get_zai_client_and_model() -> tuple[Any, str]:
    """Build a Z.AI client for image generation.

    Returns (client, model_name).
    """
    api_key = _env_first(
        ["UAGENT_ZAI_IMG_GENERATE_API_KEY", "UAGENT_ZAI_API_KEY"],
    )
    base_url = _env_first(
        [
            "UAGENT_ZAI_IMG_GENERATE_BASE_URL",
            "UAGENT_ZAI_BASE_URL",
        ],
        default="https://api.z.ai/api/paas/v4/",
    )
    model = _env_first(
        [
            "UAGENT_ZAI_IMG_GENERATE_DEPNAME",
            "UAGENT_IMG_GENERATE_DEPNAME",
        ],
        default=_DEFAULT_IMAGE_MODEL,
    )

    if not api_key:
        raise RuntimeError(
            _(
                "err.missing_env",
                default=(
                    "Missing UAGENT_ZAI_API_KEY (or UAGENT_ZAI_IMG_GENERATE_API_KEY). "
                    "Set it in .env or .env.sec."
                ),
            )
        )

    # Auto-install zai-sdk if missing
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
    except Exception as e:
        raise RuntimeError(f"Failed to initialize ZaiClient: {e}")

    return client, model


def _sanitize_size_for_zai(size: str) -> str:
    """Ensure size is compatible with GLM-Image API.

    GLM-Image: width/height must be 1024-2048, multiples of 32.
    Recommended: 1280x1280, 1568x1056, 1056x1568, 1472x1088, 1088x1472,
    1728x960, 960x1728.
    """
    if not size or "x" not in size.lower():
        return _DEFAULT_SIZE
    parts = size.lower().split("x")
    if len(parts) != 2:
        return _DEFAULT_SIZE
    try:
        w, h = int(parts[0]), int(parts[1])
    except ValueError:
        return _DEFAULT_SIZE

    # Map common OpenAI sizes to GLM-Image recommended sizes
    size_map = {
        (1024, 1024): (1280, 1280),
        (1024, 1536): (1056, 1568),
        (1536, 1024): (1568, 1056),
        (1024, 1792): (960, 1728),
        (1792, 1024): (1728, 960),
    }
    if (w, h) in size_map:
        w, h = size_map[(w, h)]

    # Clamp to 1024-2048
    w = max(1024, min(2048, w))
    h = max(1024, min(2048, h))

    # Round to multiples of 32
    w = (w // 32) * 32
    h = (h // 32) * 32

    return f"{w}x{h}"


def generate_image_zai(
    *,
    prompt: str,
    size: str,
    n: int,
    quality: str = "",
) -> dict[str, Any]:
    """Generate images using Z.AI GLM-Image API.

    Returns dict with:
      - ok: True/False
      - url_list: list of image URLs (Z.AI returns URLs, not base64)
      - items: metadata for each generated image
      - error: error message if ok=False
    """
    client, model = _get_zai_client_and_model()
    size2 = _sanitize_size_for_zai(size)

    gen_kwargs: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size2,
        "n": n,
    }

    # GLM-Image default is "hd"; only pass if explicitly set
    if quality:
        q = quality.strip().lower()
        if q in ("hd", "standard"):
            gen_kwargs["quality"] = q

    try:
        resp = client.images.generations(**gen_kwargs)
    except Exception as e:
        err = str(e)
        return {
            "ok": False,
            "error": f"Z.AI image generation failed: {err[:300]}",
            "url_list": [],
            "items": [],
        }

    url_list: list[str] = []
    items: list[dict[str, Any]] = []

    data_list = getattr(resp, "data", None) or []
    for idx, item in enumerate(data_list, start=1):
        item_meta: dict[str, Any] = {"index": idx}
        url = getattr(item, "url", None)
        if url:
            url_list.append(url)
            item_meta["url"] = url
        revised_prompt = getattr(item, "revised_prompt", None)
        if revised_prompt:
            item_meta["revised_prompt"] = revised_prompt
        items.append(item_meta)

    if not url_list:
        return {
            "ok": False,
            "error": "Z.AI returned no image URLs (resp.data is empty or url is missing)",
            "url_list": [],
            "items": items,
        }

    return {
        "ok": True,
        "url_list": url_list,
        "items": items,
    }
