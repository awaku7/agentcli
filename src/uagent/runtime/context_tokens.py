"""Dependency-light token estimation for context telemetry and budgeting."""

from __future__ import annotations

import re
from typing import Any

_WORD_RE = re.compile(r"\s+|[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def _heuristic_tokens(text: str) -> int:
    """Estimate tokens without optional tokenizer dependencies."""
    if not text:
        return 0
    cjk = len(_WORD_RE.findall(text))
    non_cjk = max(0, len(text) - cjk)
    return max(1, int(round(cjk + non_cjk / 4.0)))


def _provider_token_count(text: str, *, provider: str, model: str) -> int | None:
    """Use an installed provider-aware tokenizer when one is available."""
    provider_name = str(provider or "").strip().casefold()
    model_name = str(model or "").strip()
    if not provider_name and not model_name:
        return None

    # llmcapa already supports several configured provider/model families and
    # is optional. Import lazily so the runtime remains dependency-free.
    try:
        import llmcapa

        count = llmcapa.count_tokens(text, model_name)
        if count is not None:
            return max(0, int(count))
    except Exception:
        pass

    if provider_name in {"openai", "azure", "azure_openai", "openrouter"}:
        try:
            import tiktoken

            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except Exception:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            pass
    return None


def estimate_tokens(value: Any, *, provider: str = "", model: str = "") -> int:
    """Estimate tokens using provider/model metadata when possible.

    Optional tokenizers are used only when installed. The deterministic
    character heuristic remains the fallback, preserving offline operation.
    """
    text = str(value or "")
    if not text:
        return 0
    provider_count = _provider_token_count(text, provider=provider, model=model)
    if provider_count is not None:
        return provider_count
    return _heuristic_tokens(text)


__all__ = ["estimate_tokens"]
