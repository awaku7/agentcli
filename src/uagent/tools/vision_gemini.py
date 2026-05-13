# tools/vision_gemini.py
from __future__ import annotations
import os
from typing import Optional

from ..env_utils import env_get
from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


def _img_env(
    provider: str, mode: str, name: str, *, required: bool, default: str = ""
) -> str:
    p = provider.strip().upper()
    m = mode.strip().upper()
    n = name.strip().upper()
    keys = [f"UAGENT_{p}_IMG_{m}_{n}", f"UAGENT_{p}_{n}"]
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    if required:
        raise RuntimeError(
            _(
                "err.missing_env",
                default="Missing required env var(s): {keys}",
                keys=keys,
            )
        )
    return default


def analyze_image_gemini(
    provider: str,
    image_path: str,
    prompt: Optional[str] = None,
) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            _("err.not_installed", default="google-genai package is not installed.")
        )

    # Get API key and deployment name (model)
    api_key = _img_env(provider, "analysis", "api_key", required=False)
    if not api_key and provider == "gemini":
        api_key = env_get("UAGENT_GEMINI_API_KEY")
    elif not api_key and provider == "vertexai":
        api_key = env_get("UAGENT_VERTEXAI_API_KEY")

    model_name = _img_env(provider, "analysis", "depname", required=False)
    if not model_name:
        if provider == "vertexai":
            model_name = "gemini-1.5-flash"  # Default for Vertex AI Vision
        else:
            model_name = "gemini-1.5-flash"  # Default for Gemini AI Studio

    # Initialize client
    try:
        if provider == "vertexai":
            client = genai.Client(vertexai=True, api_key=api_key)
        else:
            client = genai.Client(api_key=api_key)
    except Exception as e:
        raise RuntimeError(
            _(
                "err.init_client",
                default="Failed to initialize Gemini/VertexAI client: {error}",
                error=e,
            )
        )

    # Read image file
    full_path = os.path.abspath(os.path.expanduser(image_path))
    if not os.path.exists(full_path):
        raise RuntimeError(
            _(
                "err.image_not_found",
                default="Image file not found: {image_path}",
                image_path=image_path,
            )
        )

    with open(full_path, "rb") as f:
        image_bytes = f.read()

    # Determine mime type
    mime_type = "image/jpeg"
    if full_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif full_path.lower().endswith(".webp"):
        mime_type = "image/webp"

    # Call Gemini
    final_prompt = prompt or "Please describe this image in detail."

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                final_prompt,
            ],
        )
        return response.text or _(
            "result.no_description", default="[No description generated]"
        )
    except Exception as e:
        return _(
            "err.analysis", default="Error during image analysis: {error}", error=e
        )
