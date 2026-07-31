from __future__ import annotations

from typing import Any

from ..env_utils import env_get


def _parse_float_env(*names: str, default: float) -> float:
    for name in names:
        raw = (env_get(name, "") or "").strip()
        if not raw:
            continue
        try:
            return float(raw)
        except Exception:
            continue
    return float(default)


def _parse_int_env(*names: str, default: int) -> int:
    for name in names:
        raw = (env_get(name, "") or "").strip()
        if not raw:
            continue
        try:
            return int(raw)
        except Exception:
            continue
    return int(default)


def _resolve_ollama_max_tokens(model: str | None = None) -> int | None:
    """Resolve an output-token limit for Ollama.

    Priority: ``UAGENT_OLLAMA_NUM_PREDICT`` / ``UAGENT_MAX_TOKENS`` (clamped
    to the model's llmcapa ``max_output_tokens``), then llmcapa's
    ``max_output_tokens`` itself. Returns ``None`` when nothing is known.
    """
    try:
        from uagent.llmcapa_util import (
            clamp_max_tokens,
            current_model,
            get_max_output_tokens,
        )

        mid = (model or "").strip() or current_model("ollama")
        num_predict = _parse_int_env(
            "UAGENT_OLLAMA_NUM_PREDICT", "UAGENT_MAX_TOKENS", default=0
        )
        if num_predict > 0:
            return clamp_max_tokens(num_predict, mid, "ollama")
        return get_max_output_tokens(mid, "ollama")
    except Exception:
        return None


def _ollama_extra_params() -> dict[str, Any]:
    """Build Ollama-specific request params from environment variables."""

    num_ctx = _parse_int_env("UAGENT_OLLAMA_NUM_CTX", default=8192)
    try:
        from uagent.llmcapa_util import (
            current_model,
            get_context_window,
        )

        mid = current_model("ollama")
        ctx = get_context_window(mid, "ollama")
        if ctx is not None and ctx > 0:
            # Keep user override, but never exceed known context window.
            num_ctx = min(num_ctx, ctx) if num_ctx > 0 else ctx
    except Exception:
        pass

    params = {
        "keep_alive": (env_get("UAGENT_OLLAMA_KEEP_ALIVE", "5m") or "5m"),
        "options": {
            "temperature": _parse_float_env(
                "UAGENT_OLLAMA_TEMPERATURE", "UAGENT_TEMPERATURE", default=0.7
            ),
            "top_p": _parse_float_env(
                "UAGENT_OLLAMA_TOP_P", "UAGENT_TOP_P", default=0.9
            ),
            "top_k": _parse_int_env("UAGENT_OLLAMA_TOP_K", default=40),
            "repeat_penalty": _parse_float_env(
                "UAGENT_OLLAMA_REPEAT_PENALTY", default=1.1
            ),
            "num_ctx": num_ctx,
            "num_keep": _parse_int_env("UAGENT_OLLAMA_NUM_KEEP", default=256),
        },
    }

    reasoning = (env_get("UAGENT_REASONING", "") or "").strip().lower()
    if reasoning and reasoning != "off":
        params["options"]["think"] = True

    return params


def apply_ollama_extra_body(chat_kwargs: dict[str, Any], *, provider: str) -> None:
    """Apply Ollama-specific ChatCompletions request options via extra_body."""

    if provider != "ollama":
        return

    try:
        extra_body = chat_kwargs.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        extra_body.update(_ollama_extra_params())
        chat_kwargs["extra_body"] = extra_body

        # Ollama's OpenAI-compatible endpoint (/v1/chat/completions) ignores
        # ``options`` inside extra_body; only the top-level ``max_tokens``
        # field is honored (mapped to num_predict internally). When no
        # explicit limit was already set, fall back to llmcapa's
        # max_output_tokens instead of a hardcoded default.
        if "max_tokens" not in chat_kwargs:
            limit = _resolve_ollama_max_tokens(chat_kwargs.get("model"))
            if limit:
                chat_kwargs["max_tokens"] = limit
    except Exception:
        pass


def ollama_fim_generate(
    *,
    base_url: str,
    model: str,
    prefix: str,
    suffix: str,
    language: str = "",
    max_tokens: int = 512,
) -> str:
    """Fill-in-the-Middle (FIM) completion via Ollama /api/generate.

    Uses the ``suffix`` parameter supported by Ollama for FIM-capable
    models (CodeGemma, StarCoder2, DeepSeek-Coder, Qwen2.5-Coder, etc.).

    Args:
        base_url: Ollama server base URL (e.g. ``http://localhost:11434``).
        model: Model name (e.g. ``codegemma:2b``).
        prefix: Code before the cursor.
        suffix: Code after the cursor.
        language: Programming language hint (unused by Ollama, reserved).
        max_tokens: Maximum tokens in the completion.

    Returns:
        The generated completion text (the ``middle`` part).
    """
    import requests

    try:
        from uagent.llmcapa_util import clamp_max_tokens

        max_tokens = clamp_max_tokens(max_tokens, model, "ollama")
    except Exception:
        pass

    payload = {
        "model": model,
        "prompt": prefix,
        "suffix": suffix,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
        },
    }

    try:
        resp = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama FIM request failed: {exc}") from exc
