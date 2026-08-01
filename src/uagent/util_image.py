"""Image / multimodal message helpers (moved from util_tools.py)."""

from __future__ import annotations

import base64
import mimetypes
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .env_utils import env_get
from .i18n import _

# Default translation function used when core.tr is not provided.
tr = _
tr_ = _

_IMAGE_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:\\|\\\\|\.\/|\.\\)?(?:\"[^\"]+\"|'[^']+'|[^\s\"']+\.(?:png|jpg|jpeg|gif|webp)))",
    re.IGNORECASE,
)


def extract_image_paths(text: str) -> list[str]:
    """テキストから画像ファイルっぽいパスを抽出（ゆるめ）。"""
    if not text:
        return []

    # JSONっぽい出力に備えて先に余計な記号を軽く剥がす
    cleaned = text.replace("\r", "")

    paths: list[str] = []
    for m in _IMAGE_PATH_RE.finditer(cleaned):
        p = m.group("path")
        if not p:
            continue

        # 末尾に句読点などが付くケースの除去（例: "/a.png,")
        p = p.rstrip(',.;:)]}>"')
        p = p.lstrip('"')

        # 重複排除（順序維持）
        if p not in paths:
            paths.append(p)

    return paths


def open_image_with_default_app(path: str) -> bool:
    """Windows の既定アプリでファイルを開く。成功/失敗を返す。"""
    try:
        expanded = os.path.expandvars(os.path.expanduser(path))
        abspath = os.path.abspath(expanded)

        if not os.path.exists(abspath):
            return False

        # Windows は os.startfile が最も直接的。
        if os.name == "nt" and hasattr(os, "startfile"):
            os.startfile(abspath)  # type: ignore[attr-defined]
            return True

        # フォールバック。
        subprocess.Popen(
            ["xdg-open", abspath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    """Convert a local image file to a data URL (base64).

    Safety:
    - Enforces max_bytes to avoid huge payloads.
    - Requires that the file exists and is a file.

    Returns:
      data:<mime>;base64,<payload>
    """

    p = Path(str(path))
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(tr("image file not found: %(path)s") % {"path": path})

    size = p.stat().st_size
    if size > int(max_bytes):
        raise ValueError(
            tr("image file too large: %(size)d bytes (limit=%(max)d)")
            % {"size": size, "max": max_bytes}
        )

    mt, mime_subtype = mimetypes.guess_type(str(p))
    mime_type = mt or "application/octet-stream"

    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def provider_allows_chat_vision(
    provider: str,
    *,
    use_responses_api: bool | None = None,
    model_id: str | None = None,
) -> bool:
    """Return True if main-chat image auto-attach is allowed for this provider.

    CHAT_VISION_PROVIDERS (openai/azure/openrouter/grok/claude/gemini/vertexai)
    already convert multimodal content at the provider layer and do not require
    UAGENT_RESPONSES.  Other RESPONSES_PROVIDERS still need Responses enabled.

    When ``model_id`` is given (or resolvable from env) and llmcapa knows the
    model, vision/image-input support is required in addition to provider gating.
    Unknown models keep the provider-level allow decision.
    """
    from .providers.provider_caps import CHAT_VISION_PROVIDERS, RESPONSES_PROVIDERS
    from .llmcapa_util import supports_vision, current_model

    prov = (provider or "").strip().lower()
    if use_responses_api is None:
        use_responses_api = (env_get("UAGENT_RESPONSES") or "").strip().lower() in (
            "1",
            "true",
        )

    if prov in CHAT_VISION_PROVIDERS:
        provider_ok = True
    else:
        provider_ok = bool(use_responses_api) and prov in RESPONSES_PROVIDERS
    if not provider_ok:
        return False

    mid = (model_id or "").strip() or current_model(prov)
    if not mid:
        return True
    vision = supports_vision(mid, prov, default=None)
    if vision is None:
        return True
    return bool(vision)


def build_multimodal_user_message(
    text: str,
    image_paths: list[str],
    *,
    provider: str,
    use_responses_api: bool | None = None,
    max_bytes: int = 10_000_000,
) -> dict[str, Any]:
    """Build a user message with embedded local images for the given provider.

    Formats by provider path:
    - gemini/vertexai: content stays a string; images go in attachments
    - Responses API: input_image parts (image_url as string data URL)
    - Chat Completions / Claude / Grok: image_url parts (image_url as {url})
    """
    from .providers.provider_caps import RESPONSES_PROVIDERS

    prov = (provider or "").strip().lower()
    if use_responses_api is None:
        use_responses_api = (env_get("UAGENT_RESPONSES") or "").strip().lower() in (
            "1",
            "true",
        )

    text_s = text if isinstance(text, str) else ("" if text is None else str(text))
    paths = [p for p in (image_paths or []) if isinstance(p, str) and p.strip()]

    # Gemini / Vertex AI: provider layer only reads message["attachments"].
    if prov in ("gemini", "vertexai"):
        attachments: list[dict[str, Any]] = []
        warn_bits: list[str] = []
        for path in paths:
            try:
                data_url = image_file_to_data_url(path, max_bytes=max_bytes)
                attachments.append(
                    {
                        "type": "image",
                        "data_url": data_url,
                        "path": path,
                        "saved_path": path,
                    }
                )
            except Exception as e:
                warn_bits.append(
                    "[WARN] "
                    + (
                        tr("Failed to attach image: %(path)s (%(etype)s: %(err)s)")
                        % {
                            "path": path,
                            "etype": type(e).__name__,
                            "err": e,
                        }
                    )
                )
        content = text_s
        if warn_bits:
            sep = "\n\n"
            nl = "\n"
            content = (content.rstrip() + sep if content else "") + nl.join(warn_bits)
        msg: dict[str, Any] = {"role": "user", "content": content}
        if attachments:
            msg["attachments"] = attachments
        return msg

    use_responses_parts = bool(use_responses_api) and prov in RESPONSES_PROVIDERS
    parts: list[dict[str, Any]] = [{"type": "text", "text": text_s}]
    for path in paths:
        try:
            data_url = image_file_to_data_url(path, max_bytes=max_bytes)
            if use_responses_parts:
                # Responses API expects input_image with image_url as a string.
                parts.append({"type": "input_image", "image_url": data_url})
            else:
                # Chat Completions / Claude / Grok multimodal shape.
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        except Exception as e:
            parts.append(
                {
                    "type": "text",
                    "text": "[WARN] "
                    + (
                        tr("Failed to attach image: %(path)s (%(etype)s: %(err)s)")
                        % {
                            "path": path,
                            "etype": type(e).__name__,
                            "err": e,
                        }
                    ),
                }
            )
    return {"role": "user", "content": parts}


def try_open_images_from_text(text: str) -> None:
    """Deprecated no-op: assistant-text image auto-open was removed."""
    return
