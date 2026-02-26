# tools/analyze_image_tool.py
from __future__ import annotations

import os
from typing import Any, Dict, List

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)


BUSY_LABEL = True


TOOL_SPEC: Dict[str, Any] = {
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
                        default="What you want to know about the image (e.g., 'Read the error message in this image', 'Describe the UI layout'). If omitted, it will default to 'Please describe this image in detail'.",
                    ),
                },
            },
            "required": ["image_path"],
        },
    },
}


def _env_first(keys: List[str], *, required: bool, default: str = "") -> str:
    for k in keys:
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    if required:
        raise RuntimeError(f"Missing required env var(s): {keys}")
    return default


def run_tool(args: Dict[str, Any]) -> str:
    image_path = str(args.get("image_path") or "")
    prompt = args.get("prompt")
    if prompt is not None:
        prompt = str(prompt)

    # If using Responses API wrapper, route to internal runtime.
    if (os.environ.get("UAGENT_RESPONSES", "") or "").strip().lower() in (
        "1",
        "true",
    ):
        # Lazy import to avoid heavy deps on tool import.
        from .vision_runtime import analyze_image_runtime

        return analyze_image_runtime(image_path=image_path, prompt=prompt)

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

    if provider.lower() == "openai":
        from .vision_openai import analyze_image_openai

        return analyze_image_openai(image_path=image_path, prompt=prompt)

    raise RuntimeError(f"Unsupported provider: {provider}")
