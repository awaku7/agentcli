from __future__ import annotations

from typing import Any, Dict

from .env_utils import env_get


def _parse_float_env(name: str, default: float) -> float:
    raw = (env_get(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _parse_int_env(name: str, default: int) -> int:
    raw = (env_get(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _ollama_extra_params() -> Dict[str, Any]:
    """Build Ollama-specific request params from environment variables."""

    params = {
        "keep_alive": (env_get("UAGENT_OLLAMA_KEEP_ALIVE", "5m") or "5m"),
        "options": {
            "temperature": _parse_float_env("UAGENT_OLLAMA_TEMPERATURE", 0.7),
            "top_p": _parse_float_env("UAGENT_OLLAMA_TOP_P", 0.9),
            "top_k": _parse_int_env("UAGENT_OLLAMA_TOP_K", 40),
            "repeat_penalty": _parse_float_env("UAGENT_OLLAMA_REPEAT_PENALTY", 1.1),
            "num_ctx": _parse_int_env("UAGENT_OLLAMA_NUM_CTX", 8192),
            "num_keep": _parse_int_env("UAGENT_OLLAMA_NUM_KEEP", 256),
            "num_predict": _parse_int_env("UAGENT_OLLAMA_NUM_PREDICT", 1024),
        },
    }

    reasoning = (env_get("UAGENT_REASONING", "") or "").strip().lower()
    if reasoning and reasoning != "off":
        params["options"]["think"] = True

    return params


def apply_ollama_extra_body(chat_kwargs: Dict[str, Any], *, provider: str) -> None:
    """Apply Ollama-specific ChatCompletions request options via extra_body."""

    if provider != "ollama":
        return

    try:
        extra_body = chat_kwargs.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        extra_body.update(_ollama_extra_params())
        chat_kwargs["extra_body"] = extra_body
    except Exception:
        pass
