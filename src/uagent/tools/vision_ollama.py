# -*- coding: utf-8 -*-
"""vision_ollama.py

Image analysis backend for Ollama native API.

This module is used by tools/analyze_image_tool.py when provider=ollama.

Notes:
- Uses Ollama native HTTP API (/api/chat).
- Sends the image as a base64 image entry in the Ollama multimodal format.
- This avoids relying on OpenAI-compatible Responses support for Ollama.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import requests

from ..env_utils import env_get
from ..providers.llm_ollama import _ollama_extra_params
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _image_file_to_base64(path: str, *, max_bytes: int = 10_000_000) -> str:
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

    data = p.read_bytes()
    return base64.b64encode(data).decode("ascii")


def _ollama_base_url() -> str:
    base_url = (
        env_get("UAGENT_OLLAMA_BASE_URL", "http://localhost:11434/v1") or ""
    ).strip()
    if not base_url:
        base_url = "http://localhost:11434/v1"

    base_url = base_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    return base_url.rstrip("/")


def analyze_image_ollama(*, image_path: str, prompt: str | None) -> str:
    """Analyze an image using Ollama native chat API."""

    provider = (env_get("UAGENT_PROVIDER") or "").strip().lower()
    if provider != "ollama":
        raise RuntimeError(
            _(
                "err.unsupported_provider",
                default="Unsupported provider for analyze_image (ollama): {provider!r}",
            ).format(provider=provider)
        )

    text = (prompt or "").strip() or _(
        "prompt.default",
        default="Please describe this image in detail.",
    )
    image_b64 = _image_file_to_base64(image_path)

    model = (env_get("UAGENT_OLLAMA_DEPNAME", "llama3.1") or "llama3.1").strip()
    if not model:
        raise RuntimeError(
            _(
                "err.missing_env.ollama",
                default="Missing required env var for ollama image analysis (UAGENT_OLLAMA_DEPNAME)",
            )
        )

    timeout_sec = 60.0
    try:
        timeout_sec = float(
            (env_get("UAGENT_OLLAMA_TIMEOUT_SEC", "60.0") or "60.0").strip() or 60.0
        )
    except Exception:
        timeout_sec = 60.0

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": text,
                "images": [image_b64],
            }
        ],
        "stream": False,
    }
    payload.update(_ollama_extra_params())

    try:
        resp = requests.post(
            f"{_ollama_base_url()}/api/chat",
            json=payload,
            timeout=timeout_sec,
        )
    except Exception as e:
        raise RuntimeError(
            _(
                "err.request_failed",
                default="Failed to call Ollama API: {err}",
            ).format(err=repr(e))
        )

    if resp.status_code >= 400:
        body = ""
        try:
            body = resp.text[:4000]
        except Exception:
            body = ""
        raise RuntimeError(
            _(
                "err.http_error",
                default="Ollama API error: HTTP {status} {body}",
            ).format(status=resp.status_code, body=body)
        )

    data: dict[str, Any]
    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(
            _(
                "err.invalid_json",
                default="Ollama API returned invalid JSON: {err}",
            ).format(err=repr(e))
        )

    out = ""
    try:
        msg = data.get("message")
        if isinstance(msg, dict):
            out = str(msg.get("content") or "")
        if not out:
            out = str(data.get("response") or "")
    except Exception:
        out = ""

    return (out or "").strip() or _(
        "warn.empty_response", default="[WARN] empty response"
    )
