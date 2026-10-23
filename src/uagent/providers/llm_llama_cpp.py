from __future__ import annotations

import json
from typing import Any

from ..env_utils import env_get


def normalize_llama_cpp_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project system context into one leading message for llama.cpp endpoints.

    Some OpenAI-compatible gateways used with the ``llama_cpp`` provider (in
    particular LiteLLM's Hosted vLLM route) reject a request if it contains a
    system message anywhere except the first entry.  uagent can accumulate
    system context from prompts, hooks, memory, and runtime projections, so
    collapse that context into one system message while leaving dialog order
    unchanged.  The input history is not mutated.
    """
    system_messages: list[dict[str, Any]] = []
    dialog_messages: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            system_messages.append(message)
        else:
            dialog_messages.append(message)

    if not system_messages:
        return list(messages)

    leading_system = dict(system_messages[0])
    if len(system_messages) > 1:
        contents: list[str] = []
        for message in system_messages:
            content = message.get("content")
            if isinstance(content, str):
                contents.append(content)
            elif content is not None:
                contents.append(json.dumps(content, ensure_ascii=False, default=str))
        leading_system["content"] = "\n\n".join(contents)

    return [leading_system, *dialog_messages]


def _float(name: str, default: float) -> float | None:
    raw = (env_get(name, "") or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int(name: str, default: int) -> int | None:
    raw = (env_get(name, "") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _llama_cpp_output_format(
    messages: list[dict[str, Any]] | None = None, model_id: str = ""
) -> Any:
    """Build llama-server JSON output format from shared Structured Output."""

    from ..runtime.capability_resolver import (
        native_structured_output_request_for_runtime,
    )

    output_format = native_structured_output_request_for_runtime(
        messages or [], model_id=model_id, provider="llama_cpp"
    )
    if output_format is not None:
        return output_format
    return None


def apply_llama_cpp_extra_body(
    chat_kwargs: dict[str, Any],
    *,
    provider: str,
    messages: list[dict[str, Any]] | None = None,
) -> None:
    """Pass llama-server sampling options through OpenAI extra_body."""
    if provider != "llama_cpp":
        return
    extra = chat_kwargs.get("extra_body")
    if not isinstance(extra, dict):
        extra = {}
    options: dict[str, Any] = {}
    top_k = _int("UAGENT_LLAMA_CPP_TOP_K", 0)
    min_p = _float("UAGENT_LLAMA_CPP_MIN_P", 0.0)
    repeat_penalty = _float("UAGENT_LLAMA_CPP_REPEAT_PENALTY", 0.0)
    if top_k is not None and top_k > 0:
        options["top_k"] = top_k
    if min_p is not None and min_p > 0:
        options["min_p"] = min_p
    if repeat_penalty is not None and repeat_penalty > 0:
        options["repeat_penalty"] = repeat_penalty
    output_format = _llama_cpp_output_format(
        messages, model_id=str(chat_kwargs.get("model", ""))
    )
    if output_format is not None and "response_format" not in extra:
        extra["response_format"] = output_format

    grammar = (env_get("UAGENT_LLAMA_CPP_GRAMMAR", "") or "").strip()
    if grammar and "grammar" not in extra:
        extra["grammar"] = grammar

    if options or output_format is not None or grammar:
        extra.update(options)
        chat_kwargs["extra_body"] = extra
