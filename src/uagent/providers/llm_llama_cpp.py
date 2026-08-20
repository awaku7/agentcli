from __future__ import annotations

from typing import Any

from ..env_utils import env_get


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


def _llama_cpp_output_format(messages: list[dict[str, Any]] | None = None) -> Any:
    """Build llama-server JSON output format from shared Structured Output."""

    from .structured_output import structured_output_request

    output_format = structured_output_request(messages or [])
    if output_format is not None:
        return output_format
    return None


def apply_llama_cpp_extra_body(
    chat_kwargs: dict[str, Any], *, provider: str, messages: list[dict[str, Any]] | None = None
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
    output_format = _llama_cpp_output_format(messages)
    if output_format is not None and "response_format" not in extra:
        extra["response_format"] = output_format

    grammar = (env_get("UAGENT_LLAMA_CPP_GRAMMAR", "") or "").strip()
    if grammar and "grammar" not in extra:
        extra["grammar"] = grammar

    if options or output_format is not None or grammar:
        extra.update(options)
        chat_kwargs["extra_body"] = extra
