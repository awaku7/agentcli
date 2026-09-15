"""Provider projection policy for OpenAI-compatible registry requests.

This module owns translation from UAGENT request policy to the native request
fields consumed by the OpenAI/Azure runtime adapter.  It deliberately does
not call an SDK or mutate messages; transport-specific serialization remains
inside the provider runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import llmcapa_util
from ..env_utils import env_get
from ..llm_helpers import (
    _choose_auto_effort,
    _extract_latest_user_text,
    _is_thinking_task,
)
from . import structured_output


@dataclass(frozen=True)
class OpenAIProjection:
    """Typed policy output used to build one OpenAI-compatible request."""

    options: dict[str, Any]
    reasoning: str
    auto_user_text: str
    effort_used: str | None


def build_openai_projection(
    *,
    provider: str,
    model: str,
    transport: str,
    messages: list[dict[str, Any]],
    send_tools: bool,
    compaction_threshold: int,
) -> OpenAIProjection:
    """Project environment and semantic request policy into native options.

    The returned mapping is provider-adapter input only.  This function has no
    network side effects and never changes ``messages``.
    """
    use_responses_api = (transport or "").strip().lower() == "responses"
    options: dict[str, Any] = {}
    reasoning = (env_get("UAGENT_REASONING", "") or "").strip().lower()
    auto_user_text = ""
    effort_used: str | None = None
    if reasoning == "auto":
        auto_user_text = _extract_latest_user_text(messages)
        if _is_thinking_task(auto_user_text):
            effort_used = _choose_auto_effort(auto_user_text)
    elif reasoning and reasoning not in {"off", "false", "none"}:
        effort_used = reasoning

    if effort_used:
        if use_responses_api:
            options["reasoning"] = {"effort": effort_used}
        else:
            options["reasoning_effort"] = effort_used

    response_format = structured_output.native_structured_output_request(
        messages, model_id=model, provider=provider
    )
    if response_format is not None:
        if use_responses_api:
            if response_format.get("type") == "json_schema":
                schema = response_format["json_schema"]
                options["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": schema["name"],
                        "strict": schema["strict"],
                        "schema": schema["schema"],
                    }
                }
            else:
                options["text"] = {"format": {"type": "json_object"}}
        else:
            options["response_format"] = response_format

    verbosity = (env_get("UAGENT_VERBOSITY", "") or "").strip().lower()
    if use_responses_api and verbosity in {"low", "medium", "high"}:
        text = options.get("text")
        text = dict(text) if isinstance(text, dict) else {}
        text["verbosity"] = verbosity
        options["text"] = text

    max_tokens = (env_get("UAGENT_MAX_TOKENS", "") or "").strip()
    if max_tokens:
        try:
            limit = llmcapa_util.clamp_max_tokens(int(max_tokens), model, provider)
            if use_responses_api:
                options["max_output_tokens"] = limit
            elif str(model or "").lower().startswith(("gpt-5", "o1", "o2", "o3", "o4")):
                options["max_completion_tokens"] = limit
            else:
                options["max_tokens"] = limit
        except ValueError:
            pass

    top_p = (env_get("UAGENT_TOP_P", "") or "").strip()
    if not use_responses_api and top_p:
        try:
            options["top_p"] = float(top_p)
        except ValueError:
            pass

    if provider == "openai" and (
        env_get("UAGENT_OPENAI_FAST_MODE", "") or ""
    ).strip().lower() in {"1", "true", "yes", "on", "fast"}:
        options["service_tier"] = "fast"

    if use_responses_api:
        options["context_management"] = [
            {"type": "compaction", "compact_threshold": compaction_threshold}
        ]

    if send_tools:
        options["tool_choice"] = "auto"
        if not use_responses_api:
            options["reasoning_effort"] = "none"

    return OpenAIProjection(
        options=options,
        reasoning=reasoning,
        auto_user_text=auto_user_text,
        effort_used=effort_used,
    )


__all__ = ["OpenAIProjection", "build_openai_projection"]
