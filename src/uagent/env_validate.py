# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .env_utils import env_get
from .i18n import _


@dataclass(frozen=True)
class MissingEnv:
    name: str
    reason: str


def _get(name: str) -> str:
    return env_get(name) or ""


def _require(names: Sequence[str], reason: str) -> list[MissingEnv]:
    missing: list[MissingEnv] = []
    for n in names:
        if not _get(n):
            missing.append(MissingEnv(name=n, reason=reason))
    return missing


def detect_provider_allow_empty() -> str:
    return _get("UAGENT_PROVIDER").lower()


def validate_startup_env() -> tuple[str, list[MissingEnv], list[str]]:
    missing: list[MissingEnv] = []
    warnings: list[str] = []
    provider = detect_provider_allow_empty()

    if not provider:
        missing += _require(
            ["UAGENT_PROVIDER"],
            reason=_(
                "Required to select the LLM provider (azure/openai/bedrock/openrouter/gemini/grok/claude/nvidia/deepseek/zai/alibaba/moonshot/mimo/lmstudio/minimax/hf).",
                default="Required to select the LLM provider (azure/openai/bedrock/openrouter/gemini/grok/claude/nvidia/deepseek/zai/alibaba/moonshot/mimo/lmstudio/minimax/hf).",
            ),
        )
        return provider, missing, warnings

    allowed = (
        "azure",
        "openai",
        "bedrock",
        "openrouter",
        "ollama",
        "gemini",
        "vertexai",
        "grok",
        "claude",
        "nvidia",
        "deepseek",
        "zai",
        "alibaba",
        "moonshot",
        "mimo",
        "lmstudio",
        "minimax",
        "hf",
    )
    if provider not in allowed:
        warnings.append(
            _(
                "Unknown provider: %(provider)r. Allowed: %(allowed)s (startup will likely fail).",
                default=f"Unknown provider: {provider!r}. Allowed: {', '.join(allowed)} (startup will likely fail).",
            )
            % {"provider": provider, "allowed": ", ".join(allowed)}
        )
        return provider, missing, warnings

    if provider == "azure":
        missing += _require(
            ["UAGENT_AZURE_BASE_URL"],
            reason=_(
                "Azure OpenAI endpoint/base URL (e.g., https://<resource>.openai.azure.com/).",
                default="Azure OpenAI endpoint/base URL (e.g., https://<resource>.openai.azure.com/).",
            ),
        )
        missing += _require(
            ["UAGENT_AZURE_API_KEY"],
            reason=_("Azure OpenAI API key.", default="Azure OpenAI API key."),
        )
        missing += _require(
            ["UAGENT_AZURE_API_VERSION"],
            reason=_(
                "Azure OpenAI API version (e.g., 2024-xx-xx).",
                default="Azure OpenAI API version (e.g., 2024-xx-xx).",
            ),
        )
    elif provider == "openai":
        missing += _require(
            ["UAGENT_OPENAI_API_KEY"],
            reason=_("OpenAI API key.", default="OpenAI API key."),
        )
    elif provider == "bedrock":
        missing += _require(
            ["UAGENT_BEDROCK_BASE_URL"],
            reason=_(
                "Bedrock proxy endpoint/base URL (OpenAI-compatible).",
                default="Bedrock proxy endpoint/base URL (OpenAI-compatible).",
            ),
        )
        missing += _require(
            ["UAGENT_BEDROCK_API_KEY"],
            reason=_(
                "Bedrock proxy API key (OpenAI-compatible).",
                default="Bedrock proxy API key (OpenAI-compatible).",
            ),
        )
    elif provider == "openrouter":
        missing += _require(
            ["UAGENT_OPENROUTER_API_KEY"],
            reason=_("OpenRouter API key.", default="OpenRouter API key."),
        )
    elif provider == "grok":
        missing += _require(
            ["UAGENT_GROK_API_KEY"],
            reason=_("Grok (xAI) API key.", default="Grok (xAI) API key."),
        )
    elif provider == "gemini":
        missing += _require(
            ["UAGENT_GEMINI_API_KEY"],
            reason=_("Gemini API key.", default="Gemini API key."),
        )
        try:
            from google import genai as _genai  # noqa: F401
        except Exception:
            warnings.append(
                _(
                    "Python package 'google-genai' is not installed. Provider=gemini requires it.",
                    default="Python package 'google-genai' is not installed. Provider=gemini requires it.",
                )
            )
    elif provider == "vertexai":
        missing += _require(
            [
                "UAGENT_VERTEXAI_API_KEY",
                "UAGENT_VERTEXAI_DEPNAME",
            ],
            reason=_(
                "Vertex AI API key / model name.",
                default="Vertex AI API key / model name.",
            ),
        )
        try:
            from google import genai as _genai  # noqa: F401
        except Exception:
            warnings.append(
                _(
                    "Python package 'google-genai' is not installed. Provider=vertexai requires it.",
                    default="Python package 'google-genai' is not installed. Provider=vertexai requires it.",
                )
            )
    elif provider == "claude":
        missing += _require(
            ["UAGENT_CLAUDE_API_KEY"],
            reason=_(
                "Anthropic (Claude) API key.", default="Anthropic (Claude) API key."
            ),
        )
        try:
            from anthropic import Anthropic as _Anthropic  # noqa: F401
        except Exception:
            warnings.append(
                _(
                    "Python package 'anthropic' is not installed. Provider=claude requires it.",
                    default="Python package 'anthropic' is not installed. Provider=claude requires it.",
                )
            )
    elif provider == "nvidia":
        missing += _require(
            ["UAGENT_NVIDIA_API_KEY"],
            reason=_("NVIDIA API key.", default="NVIDIA API key."),
        )
    elif provider == "deepseek":
        missing += _require(
            ["UAGENT_DEEPSEEK_API_KEY"],
            reason=_("DeepSeek API key.", default="DeepSeek API key."),
        )
    elif provider == "zai":
        missing += _require(
            ["UAGENT_ZAI_API_KEY"],
            reason=_("Z.AI (Zhipu AI) API key.", default="Z.AI (Zhipu AI) API key."),
        )
    elif provider == "alibaba":
        missing += _require(
            ["UAGENT_ALIBABA_API_KEY"],
            reason=_(
                "Alibaba Cloud (Qwen) API key.", default="Alibaba Cloud (Qwen) API key."
            ),
        )
    elif provider == "moonshot":
        if not _get("UAGENT_MOONSHOT_API_KEY"):
            missing.append(
                MissingEnv(
                    name="UAGENT_MOONSHOT_API_KEY",
                    reason=_("Moonshot AI API key.", default="Moonshot AI API key."),
                )
            )
    elif provider == "mimo":
        missing += _require(
            ["UAGENT_MIMO_API_KEY"],
            reason=_("Xiaomi MiMo API key.", default="Xiaomi MiMo API key."),
        )
    elif provider == "minimax":
        missing += _require(
            ["UAGENT_MINIMAX_API_KEY"],
            reason=_("MiniMax API key.", default="MiniMax API key."),
        )
    elif provider == "hf":
        missing += _require(
            ["UAGENT_HF_API_KEY"],
            reason=_(
                "Hugging Face API key (HF_TOKEN).",
                default="Hugging Face API key (HF_TOKEN).",
            ),
        )

    embedding_provider = (_get("UAGENT_EMBEDDING_PROVIDER") or "").lower()
    if embedding_provider:
        embedding_allowed = (
            "openai",
            "azure",
            "bedrock",
            "openrouter",
            "ollama",
            "nvidia",
            "gemini",
            "vertexai",
        )
        if embedding_provider not in embedding_allowed:
            warnings.append(
                _(
                    "Unknown embedding provider: %(provider)r. Allowed: %(allowed)s (startup will likely fail).",
                    default=f"Unknown embedding provider: {embedding_provider!r}. Allowed: {', '.join(embedding_allowed)} (startup will likely fail).",
                )
                % {
                    "provider": embedding_provider,
                    "allowed": ", ".join(embedding_allowed),
                }
            )
        elif embedding_provider == "azure":
            missing += _require(
                [
                    "UAGENT_AZURE_EMBEDDING_BASE_URL",
                    "UAGENT_AZURE_EMBEDDING_API_KEY",
                    "UAGENT_AZURE_EMBEDDING_API_VERSION",
                    "UAGENT_AZURE_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "Azure embedding endpoint / API key / API version / deployment name.",
                    default="Azure embedding endpoint / API key / API version / deployment name.",
                ),
            )
        elif embedding_provider == "openai":
            missing += _require(
                [
                    "UAGENT_OPENAI_EMBEDDING_API_KEY",
                    "UAGENT_OPENAI_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "OpenAI embedding API key / model name.",
                    default="OpenAI embedding API key / model name.",
                ),
            )
        elif embedding_provider == "bedrock":
            missing += _require(
                [
                    "UAGENT_BEDROCK_EMBEDDING_BASE_URL",
                    "UAGENT_BEDROCK_EMBEDDING_API_KEY",
                    "UAGENT_BEDROCK_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "Bedrock embedding endpoint / API key / deployment name.",
                    default="Bedrock embedding endpoint / API key / deployment name.",
                ),
            )
        elif embedding_provider == "openrouter":
            missing += _require(
                [
                    "UAGENT_OPENROUTER_EMBEDDING_API_KEY",
                    "UAGENT_OPENROUTER_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "OpenRouter embedding API key / model name.",
                    default="OpenRouter embedding API key / model name.",
                ),
            )
        elif embedding_provider == "ollama":
            missing += _require(
                [
                    "UAGENT_OLLAMA_EMBEDDING_BASE_URL",
                    "UAGENT_OLLAMA_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "Ollama embedding base URL / model name.",
                    default="Ollama embedding base URL / model name.",
                ),
            )
        elif embedding_provider == "nvidia":
            missing += _require(
                [
                    "UAGENT_NVIDIA_EMBEDDING_API_KEY",
                    "UAGENT_NVIDIA_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "NVIDIA embedding API key / model name.",
                    default="NVIDIA embedding API key / model name.",
                ),
            )
        elif embedding_provider == "gemini":
            missing += _require(
                [
                    "UAGENT_GEMINI_EMBEDDING_API_KEY",
                    "UAGENT_GEMINI_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "Gemini embedding API key / model name.",
                    default="Gemini embedding API key / model name.",
                ),
            )
        elif embedding_provider == "vertexai":
            missing += _require(
                [
                    "UAGENT_VERTEXAI_EMBEDDING_API_KEY",
                    "UAGENT_VERTEXAI_EMBEDDING_DEPNAME",
                ],
                reason=_(
                    "Vertex AI embedding API key / model name.",
                    default="Vertex AI embedding API key / model name.",
                ),
            )

    return provider, missing, warnings


def format_missing_env_message(
    *,
    missing: Sequence[MissingEnv],
    warnings: Sequence[str] = (),
    context: str = "startup",
) -> str:
    lines: list[str] = []
    lines.append(
        _(
            "[FATAL] Environment validation failed ({context}).",
            default="[FATAL] Environment validation failed ({context}).",
            context=context,
        )
    )
    if missing:
        lines.append(
            _(
                "Missing required environment variables:",
                default="Missing required environment variables:",
            )
        )
        for m in missing:
            lines.append(f"- {m.name}: {m.reason}")
    if warnings:
        lines.append(_("Warnings:", default="Warnings:"))
        for w in warnings:
            lines.append(f"- {w}")
    lines.append("")
    lines.append(_("How to fix:", default="How to fix:"))
    lines.append(
        _(
            "- Set the variables above in your environment before starting the program.",
            default="- Set the variables above in your environment before starting the program.",
        )
    )
    lines.append(
        _(
            "- You can set them via your OS environment settings, a .env file, your shell startup scripts,",
            default="- You can set them via your OS environment settings, a .env file, your shell startup scripts,",
        )
    )
    lines.append(
        _(
            "  or your process manager / service configuration (CI secrets, systemd, Docker, etc.).",
            default="  or your process manager / service configuration (CI secrets, systemd, Docker, etc.).",
        )
    )
    return "\n".join(lines) + "\n"
