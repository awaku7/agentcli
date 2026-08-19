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


def apply_llama_cpp_extra_body(chat_kwargs: dict[str, Any], *, provider: str) -> None:
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
    if options:
        extra.update(options)
        chat_kwargs["extra_body"] = extra
