# tools/analyze_image_tool.py
from __future__ import annotations

from ..env_utils import env_get
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


BUSY_LABEL = True


TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": _(
            "tool.description",
            default="Load an image file and have AI (Vision) describe its contents. Useful for analyzing screenshots or reading charts/tables.",
        ),
        "system_prompt": _(
            "tool.system_prompt",
            default="This tool performs the operation described by the tool name 'analyze_image'.",
        ),
        "x_search_terms": _(
            "x_search_terms",
            default=[
                "analyze_image",
                "analyze image",
                "image",
                "picture",
                "photo",
                "diagram",
            ],
        ),
        "x_search_terms_en": [
            "analyze_image",
            "analyze image",
            "image",
            "picture",
            "photo",
            "diagram",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": _(
                        "param.image_path.description",
                        default="Path to the image file to analyze.",
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": _(
                        "param.prompt.description",
                        default="What you want to know about the image (e. g.",
                    ),
                },
            },
            "required": ["image_path"],
        },
    },
}

# When Responses API is enabled for providers that can send images directly,
# hide analyze_image to avoid redundant tool calls.
if (env_get("UAGENT_RESPONSES", "") or "").strip().lower() in ("1", "true", "yes") and (
    env_get("UAGENT_PROVIDER") or ""
).strip().lower() in ("azure", "openai", "bedrock", "openrouter", "ollama"):
    TOOL_SPEC = None  # type: ignore[assignment]


def _env_first(keys: list[str], *, required: bool, default: str = "") -> str:
    for k in keys:
        v = (env_get(k) or "").strip()
        if v:
            return v
    if required:
        raise RuntimeError(f"Missing required env var(s): {keys}")
    return default


def run_tool(args: dict[str, Any]) -> str:
    image_path = str(args.get("image_path") or "")
    prompt = args.get("prompt")
    if prompt is not None:
        prompt = str(prompt)

    provider = _env_first(
        [
            "UAGENT_IMG_ANALYSIS_PROVIDER",
            "UAGENT_PROVIDER",
        ],
        required=False,
        default="",
    )

    if not provider:
        raise RuntimeError(
            "UAGENT_IMG_ANALYSIS_PROVIDER (or UAGENT_PROVIDER) is required for analyze_image"
        )

    provider_l = provider.lower()

    if provider_l == "ollama":
        from .vision_ollama import analyze_image_ollama

        return analyze_image_ollama(
            image_path=image_path,
            prompt=prompt,
        )

    if provider_l in ("openai", "azure"):
        from .vision_openai import analyze_image_openai

        return analyze_image_openai(
            provider=provider_l,
            image_path=image_path,
            prompt=prompt,
        )

    if provider_l in ("gemini", "vertexai"):
        from .vision_gemini import analyze_image_gemini

        return analyze_image_gemini(
            provider=provider_l,
            image_path=image_path,
            prompt=prompt,
        )

    raise RuntimeError(f"Unsupported provider: {provider}")
