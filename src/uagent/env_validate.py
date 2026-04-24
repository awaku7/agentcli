# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .env_utils import env_get
from .i18n import _


@dataclass(frozen=True)
class MissingEnv:
    name: str
    reason: str


def _get(name: str) -> str:
    return env_get(name) or ""


def _require(names: Sequence[str], reason: str) -> List[MissingEnv]:
    missing: List[MissingEnv] = []
    for n in names:
        if not _get(n):
            missing.append(MissingEnv(name=n, reason=reason))
    return missing


def detect_provider_allow_empty() -> str:
    return _get("UAGENT_PROVIDER").lower()


def validate_startup_env() -> Tuple[str, List[MissingEnv], List[str]]:
    missing: List[MissingEnv] = []
    warnings: List[str] = []
    provider = detect_provider_allow_empty()

    if not provider:
        missing += _require(
            ["UAGENT_PROVIDER"],
            reason=_(
                "Required to select the LLM provider (azure/openai/bedrock/openrouter/gemini/grok/claude/nvidia).",
                default="Required to select the LLM provider (azure/openai/bedrock/openrouter/gemini/grok/claude/nvidia).",
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
    )
    if provider not in allowed:
        warnings.append(
            _(
                f"Unknown provider: {provider!r}. Allowed: {', '.join(allowed)} (startup will likely fail).",
                default=f"Unknown provider: {provider!r}. Allowed: {', '.join(allowed)} (startup will likely fail).",
                provider=provider,
                allowed=", ".join(allowed),
            )
        )
        return provider, missing, warnings

    if provider == "azure":
        missing += _require(
            ["UAGENT_AZURE_BASE_URL"],
            reason="Azure OpenAI endpoint/base URL (e.g., https://<resource>.openai.azure.com/).",
        )
        missing += _require(
            ["UAGENT_AZURE_API_KEY"],
            reason="Azure OpenAI API key.",
        )
        missing += _require(
            ["UAGENT_AZURE_API_VERSION"],
            reason="Azure OpenAI API version (e.g., 2024-xx-xx).",
        )
    elif provider == "openai":
        missing += _require(
            ["UAGENT_OPENAI_API_KEY"],
            reason="OpenAI API key.",
        )
    elif provider == "bedrock":
        missing += _require(
            ["UAGENT_BEDROCK_BASE_URL"],
            reason="Bedrock proxy endpoint/base URL (OpenAI-compatible).",
        )
        missing += _require(
            ["UAGENT_BEDROCK_API_KEY"],
            reason="Bedrock proxy API key (OpenAI-compatible).",
        )
    elif provider == "openrouter":
        missing += _require(
            ["UAGENT_OPENROUTER_API_KEY"],
            reason="OpenRouter API key.",
        )
    elif provider == "grok":
        missing += _require(
            ["UAGENT_GROK_API_KEY"],
            reason="Grok (xAI) API key.",
        )
    elif provider == "gemini":
        missing += _require(
            ["UAGENT_GEMINI_API_KEY"],
            reason="Gemini API key.",
        )
        try:
            from google import genai as _genai  # noqa: F401
        except Exception:
            warnings.append(
                "Python package 'google-genai' is not installed. Provider=gemini requires it."
            )
    elif provider == "vertexai":
        missing += _require(
            [
                "UAGENT_VERTEXAI_API_KEY",
                "UAGENT_VERTEXAI_DEPNAME",
            ],
            reason="Vertex AI API key / model name.",
        )
        try:
            from google import genai as _genai  # noqa: F401
        except Exception:
            warnings.append(
                "Python package 'google-genai' is not installed. Provider=vertexai requires it."
            )
    elif provider == "claude":
        missing += _require(
            ["UAGENT_CLAUDE_API_KEY"],
            reason="Anthropic (Claude) API key.",
        )
        try:
            from anthropic import Anthropic as _Anthropic  # noqa: F401
        except Exception:
            warnings.append(
                "Python package 'anthropic' is not installed. Provider=claude requires it."
            )
    elif provider == "nvidia":
        missing += _require(
            ["UAGENT_NVIDIA_API_KEY"],
            reason="NVIDIA API key.",
        )

    return provider, missing, warnings


def format_missing_env_message(
    *,
    missing: Sequence[MissingEnv],
    warnings: Sequence[str] = (),
    context: str = "startup",
) -> str:
    lines: List[str] = []
    lines.append(
        _(
            f"[FATAL] Environment validation failed ({context}).",
            default=f"[FATAL] Environment validation failed ({context}).",
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
            lines.append(
                _(
                    f"- {m.name}: {m.reason}",
                    default=f"- {m.name}: {m.reason}",
                    name=m.name,
                    reason=m.reason,
                )
            )
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
