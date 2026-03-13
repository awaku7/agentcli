# -*- coding: utf-8 -*-
"""vision_runtime.py

Image analysis backend for OpenAI/Azure OpenAI Responses API.

This module is used by tools/analyze_image_tool.py when UAGENT_RESPONSES=1.

Notes:
- Responses API support is limited to provider=azure/openai in this project.
- The CLI can also send images directly as user content items; this module exists
  mainly to avoid missing-import crashes if the analyze_image tool is invoked.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _image_file_to_data_url(path: str, *, max_bytes: int = 10_000_000) -> str:
    p = Path(str(path))
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(
            _("err.image_not_found", default="image file not found: {path}").format(
                path=path
            )
        )

    size = p.stat().st_size
    if size > int(max_bytes):
        raise ValueError(
            _(
                "err.image_too_large",
                default="image file too large: {size} bytes (limit={max_bytes})",
            ).format(size=size, max_bytes=int(max_bytes))
        )

    mt, _enc = mimetypes.guess_type(str(p))
    mime_type = mt or "application/octet-stream"

    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return "data:{mime_type};base64,{b64}".format(mime_type=mime_type, b64=b64)


def analyze_image_runtime(*, image_path: str, prompt: str | None) -> str:
    """Analyze an image via Responses API (OpenAI/Azure)."""

    provider = (env_get("UAGENT_PROVIDER") or "").strip().lower()
    if provider not in ("openai", "azure"):
        raise RuntimeError(
            _(
                "err.unsupported_provider",
                default=(
                    "UAGENT_RESPONSES=1 is set, but image analysis via Responses is supported only for openai/azure "
                    "(got provider={provider!r})"
                ),
            ).format(provider=provider)
        )

    try:
        from openai import AzureOpenAI, OpenAI
    except Exception as e:
        raise RuntimeError(
            _(
                "err.import_openai",
                default="Failed to import openai package: {err}",
            ).format(err=repr(e))
        )

    text = (prompt or "").strip() or _(
        "prompt.default",
        default="Please describe this image in detail.",
    )
    data_url = _image_file_to_data_url(image_path)

    if provider == "azure":
        base_url = env_get("UAGENT_AZURE_BASE_URL")
        api_key = env_get("UAGENT_AZURE_API_KEY")
        api_version = env_get("UAGENT_AZURE_API_VERSION")
        model = env_get("UAGENT_AZURE_DEPNAME")
        if not (base_url and api_key and api_version and model):
            raise RuntimeError(
                _(
                    "err.missing_env.azure",
                    default=(
                        "Missing required env vars for azure (UAGENT_AZURE_BASE_URL/API_KEY/API_VERSION/DEPNAME)"
                    ),
                )
            )
        client = AzureOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
        )
    else:
        api_key = env_get("UAGENT_OPENAI_API_KEY")
        base_url = env_get("UAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = env_get("UAGENT_OPENAI_DEPNAME")
        if not (api_key and model):
            raise RuntimeError(
                _(
                    "err.missing_env.openai",
                    default=(
                        "Missing required env vars for openai (UAGENT_OPENAI_API_KEY/DEPNAME)"
                    ),
                )
            )
        client = OpenAI(api_key=api_key, base_url=base_url)

    resp = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    )

    # Extract output_text
    out = ""
    try:
        for item in getattr(resp, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", None) == "output_text":
                        out += str(getattr(c, "text", "") or "")
    except Exception:
        out = ""

    return (out or "").strip() or _(
        "warn.empty_response", default="[WARN] empty response"
    )
