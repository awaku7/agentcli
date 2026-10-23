"""User-facing formatting for legacy provider errors."""

from __future__ import annotations

import html
import re


def provider_error_label(provider: str) -> str:
    """Return a user-facing error label for the active provider."""
    name = (provider or "").strip().lower()
    labels = {
        "alibaba": "Alibaba",
        "azure": "Azure",
        "bedrock": "Amazon Bedrock",
        "claude": "Claude",
        "deepseek": "DeepSeek",
        "foundry_local": "Foundry Local",
        "gemini": "Gemini",
        "grok": "Grok",
        "hf": "Hugging Face",
        "inception": "Inception",
        "llama_cpp": "llama.cpp",
        "lmstudio": "LM Studio",
        "meta": "Meta",
        "minimax": "MiniMax",
        "mimo": "Mimo",
        "moonshot": "Moonshot",
        "novita": "Novita",
        "nvidia": "NVIDIA",
        "ollama": "Ollama",
        "openai": "OpenAI",
        "openrouter": "OpenRouter",
        "perplexity": "Perplexity",
        "pfn": "PFN",
        "sakura": "Sakura",
        "sakana": "Sakana AI",
        "together": "Together AI",
        "vercel": "Vercel",
        "vertexai": "Vertex AI",
        "vllm": "vLLM",
        "zai": "Z.ai",
    }
    # Preserve the configured provider name for custom/future providers rather
    # than incorrectly labelling every non-Meta provider as Azure/OpenAI.
    return labels.get(name, name or "LLM")


def is_zscaler_responses_block(exc: BaseException) -> bool:
    """Detect the corporate Zscaler page returned for the Responses endpoint."""
    parts = [str(exc)]
    body = getattr(exc, "body", None)
    if body is not None:
        parts.append(str(body))
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            parts.append(str(getattr(response, "text", "") or ""))
        except Exception:
            pass
    text = " ".join(parts).lower()
    return "/v1/responses" in text and ("zscaler" in text or "website blocked" in text)


def exception_text(exc: BaseException) -> str:
    """Return a short, single-line exception summary for the UI."""
    text = str(exc).replace("\r", " ").replace("\n", " ")
    lowered = text.lower()
    if "zscaler" in lowered or "website blocked" in lowered:
        urls = re.findall(r"https?://[^\s<>\"']+", text)
        target = urls[-1] if urls else "the requested URL"
        return f"Zscaler blocked access to {target}"
    if "<!doctype html" in lowered or "<html>" in lowered:
        text = html.unescape(re.sub(r"<[^>]*>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] + ("..." if len(text) > 500 else "")


__all__ = ["exception_text", "is_zscaler_responses_block", "provider_error_label"]
