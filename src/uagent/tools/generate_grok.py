# -*- coding: utf-8 -*-
"""generate_grok.py - Image generation via xAI Grok Imagine API.

This module is used by tools/generate_image_tool.py when the provider is "grok".

Notes:
- Uses the xai-sdk (pip install xai-sdk) for image generation.
- Default image generation model is "grok-imagine-image".
  Override with UAGENT_GROK_IMG_GENERATE_DEPNAME or UAGENT_IMG_GENERATE_DEPNAME.
- OpenAI-style WxH sizes are mapped to xAI aspect_ratio (+ optional resolution).
- Prefer URL responses; caller downloads and saves as PNG (Z.AI-style).
  Base64 is also returned when available as a fallback.
- Models: grok-imagine-image | grok-imagine-image-pro | grok-imagine-image-quality
- API: client.image.sample / client.image.sample_batch
"""

from __future__ import annotations

from typing import Any

from ..auth.provider_credentials import get_provider_api_key
from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

# Default image generation model for xAI Grok Imagine
_DEFAULT_IMAGE_MODEL = "grok-imagine-image"

# Supported aspect ratios (ratio value, label)
_ASPECT_RATIOS: list[tuple[float, str]] = [
    (1.0, "1:1"),
    (16 / 9, "16:9"),
    (9 / 16, "9:16"),
    (4 / 3, "4:3"),
    (3 / 4, "3:4"),
    (3 / 2, "3:2"),
    (2 / 3, "2:3"),
    (2.0, "2:1"),
    (0.5, "1:2"),
    (20 / 9, "20:9"),
    (9 / 20, "9:20"),
    (19.5 / 9, "19.5:9"),
    (9 / 19.5, "9:19.5"),
]


def _env_first(keys: list[str], *, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    if not default:
        value = get_provider_api_key("grok") or ""
        if value:
            return value.strip()
    return default


def _get_grok_client_and_model() -> tuple[Any, str]:
    """Build an xAI client for image generation.

    Returns (client, model_name).
    """
    api_key = _env_first(
        ["UAGENT_GROK_IMG_GENERATE_API_KEY", "UAGENT_GROK_API_KEY"],
    )
    model = _env_first(
        [
            "UAGENT_GROK_IMG_GENERATE_DEPNAME",
            "UAGENT_IMG_GENERATE_DEPNAME",
        ],
        default=_DEFAULT_IMAGE_MODEL,
    )

    if not api_key:
        raise RuntimeError(
            _(
                "err.missing_env",
                default=(
                    "Missing UAGENT_GROK_API_KEY (or UAGENT_GROK_IMG_GENERATE_API_KEY). "
                    "Set it in .env or .env.sec."
                ),
            )
        )

    # Auto-install xai-sdk if missing
    from .._pip_auto import install_with_status as _install_xai_sdk

    if not _install_xai_sdk("xai-sdk", "xai_sdk", display_name="xai-sdk"):
        raise RuntimeError(
            _(
                "err.xai_import",
                default="Failed to import xai-sdk. Install with: pip install xai-sdk",
            )
        )
    from xai_sdk import Client as XAIClient

    use_insecure = False
    try:
        from ..providers.util_providers import is_ssl_verify_disabled

        use_insecure = bool(is_ssl_verify_disabled())
    except Exception:
        # Fallback: honor UAGENT_SSL_VERIFY (default off => insecure channel)
        v = (env_get("UAGENT_SSL_VERIFY") or "").strip().lower()
        use_insecure = v not in ("1", "true", "yes", "on")

    try:
        client = XAIClient(api_key=api_key, use_insecure_channel=use_insecure)
    except Exception as e:
        raise RuntimeError(
            _("grok.init_failed", default=f"Failed to initialize xAI Client: {e}")
        )

    return client, model


def _closest_aspect_ratio(width: int, height: int) -> str:
    """Map WxH to the nearest supported xAI aspect_ratio label."""
    if width <= 0 or height <= 0:
        return _("grok.aspect_11", default="1:1")
    target = width / height
    best_label = "1:1"
    best_diff = float("inf")
    for ratio, label in _ASPECT_RATIOS:
        diff = abs(ratio - target)
        if diff < best_diff:
            best_diff = diff
            best_label = label
    return best_label


def _sanitize_size_for_grok(size: str, quality: str = "") -> tuple[str, str]:
    """Map OpenAI-style size / quality to xAI (aspect_ratio, resolution).

    Returns (aspect_ratio, resolution) where resolution is "1k" or "2k".
    """
    aspect = "1:1"
    resolution = "1k"

    if size and "x" in size.lower():
        parts = size.lower().split("x")
        if len(parts) == 2:
            try:
                w, h = int(parts[0].strip()), int(parts[1].strip())
                aspect = _closest_aspect_ratio(w, h)
                # ~2 megapixels or larger edge => prefer 2k
                if max(w, h) >= 1536 or (w * h) >= 2_000_000:
                    resolution = "2k"
            except ValueError:
                pass

    q = (quality or "").strip().lower()
    if q in ("hd", "high", "2k"):
        resolution = "2k"
    elif q in ("standard", "low", "medium", "1k"):
        resolution = "1k"

    return aspect, resolution


def _extract_url(resp: Any) -> str:
    """Best-effort URL extraction without raising on moderation/missing fields."""
    try:
        url = getattr(resp, "url", None)
        if url:
            return str(url)
    except Exception:
        pass
    try:
        image = getattr(resp, "_image", None)
        if image is not None:
            url = getattr(image, "url", None) or ""
            if url:
                return str(url)
    except Exception:
        pass
    try:
        public_url = getattr(resp, "public_url", None)
        if public_url:
            return str(public_url)
    except Exception:
        pass
    return _("grok.empty2", default="")


def _extract_b64(resp: Any) -> str:
    """Best-effort base64 extraction; strip data-URI prefix if present."""
    raw = ""
    try:
        raw = getattr(resp, "base64", None) or ""
    except Exception:
        raw = ""
    if not raw:
        try:
            image = getattr(resp, "_image", None)
            if image is not None:
                raw = getattr(image, "base64", None) or ""
        except Exception:
            raw = ""
    if not raw:
        return _("grok.empty1", default="")
    s = str(raw).strip()
    if "base64," in s:
        s = s.split("base64,", 1)[1]
    return s


def generate_image_grok(
    *,
    prompt: str,
    size: str,
    n: int,
    quality: str = "",
) -> dict[str, Any]:
    """Generate images using xAI Grok Imagine API.

    Returns dict with:
      - ok: True/False
      - url_list: list of image URLs
      - b64_list: list of base64 payloads (when available)
      - items: metadata for each generated image
      - aspect_ratio / resolution: mapped request params
      - error: error message if ok=False
    """
    client, model = _get_grok_client_and_model()
    aspect_ratio, resolution = _sanitize_size_for_grok(size, quality)
    n = max(1, min(4, int(n or 1)))

    gen_kwargs: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "image_format": "url",
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }

    try:
        if n == 1:
            responses = [client.image.sample(**gen_kwargs)]
        else:
            responses = list(client.image.sample_batch(n=n, **gen_kwargs))
    except Exception as e:
        err = str(e)
        return {
            "ok": False,
            "error": f"Grok image generation failed: {err[:300]}",
            "url_list": [],
            "b64_list": [],
            "items": [],
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }

    url_list: list[str] = []
    b64_list: list[str] = []
    items: list[dict[str, Any]] = []

    for idx, resp in enumerate(responses, start=1):
        item_meta: dict[str, Any] = {"index": idx}
        try:
            item_meta["respect_moderation"] = bool(
                getattr(resp, "respect_moderation", True)
            )
        except Exception:
            pass

        url = _extract_url(resp)
        if url:
            url_list.append(url)
            item_meta["url"] = url

        b64 = _extract_b64(resp)
        if b64:
            b64_list.append(b64)
            item_meta["has_b64_json"] = True

        try:
            cost = getattr(resp, "cost_usd", None)
            if cost is not None:
                item_meta["cost_usd"] = cost
        except Exception:
            pass

        items.append(item_meta)

    if not url_list and not b64_list:
        return {
            "ok": False,
            "error": (
                "Grok returned no image data "
                "(url/base64 missing; may have failed moderation)"
            ),
            "url_list": [],
            "b64_list": [],
            "items": items,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }

    return {
        "ok": True,
        "url_list": url_list,
        "b64_list": b64_list,
        "items": items,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }
