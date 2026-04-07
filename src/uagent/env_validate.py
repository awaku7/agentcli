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
                "env.required.provider",
                default="Required to select the LLM provider (azure/openai/bedrock/openrouter/gemini/grok/claude/nvidia).",
            ),
        )
        missing += _require(
            ["UAGENT_AZURE_BASE_URL", "UAGENT_AZURE_API_KEY", "UAGENT_AZURE_API_VERSION"],
            reason=_("env.required.azure", default="(azure) Required when using Azure OpenAI."),
        )
        missing += _require(
            ["UAGENT_OPENAI_API_KEY"],
            reason=_("env.required.openai", default="(openai) Required when using OpenAI."),
        )
        missing += _require(
            ["UAGENT_OPENROUTER_API_KEY"],
            reason=_("env.required.openrouter", default="(openrouter) Required when using OpenRouter."),
        )
        missing += _require(
            ["UAGENT_GROK_API_KEY"],
            reason=_("env.required.grok", default="(grok) Required when using Grok (xAI)."),
        )
        missing += _require(
            ["UAGENT_OLLAMA_BASE_URL"],
            reason=_("env.required.ollama", default="(ollama) Required when using Ollama."),
        )
        missing += _require(
            ["UAGENT_GEMINI_API_KEY"],
            reason=_("env.required.gemini", default="(gemini) Required when using Gemini."),
        )
        missing += _require(
            ["UAGENT_CLAUDE_API_KEY"],
            reason=_("env.required.claude", default="(claude) Required when using Claude (Anthropic)."),
        )
        missing += _require(
            ["UAGENT_NVIDIA_API_KEY"],
            reason=_("env.required.nvidia", default="(nvidia) Required when using NVIDIA."),
        )
        return provider, missing, warnings

    allowed = (
        "azure",
        "openai",
        "bedrock",
        "openrouter",
        "ollama",
        "gemini",
        "grok",
        "claude",
        "nvidia",
    )
    if provider not in allowed:
        warnings.append(
            _(
                "env.warn.unknown_provider",
                default=f"Unknown provider: {provider!r}. Allowed: {', '.join(allowed)} (startup will likely fail).",
                provider=provider,
                allowed=", ".join(allowed),
            )
        )
        return provider, missing, warnings

    if provider == "azure":
        missing += _require(
            ["UAGENT_AZURE_BASE_URL"],
            reason=_(
                "env.azure.base_url",
                default="Azure OpenAI endpoint/base URL (e.g., https://<resource>.openai.azure.com/).",
            ),
        )
        missing += _require(
            ["UAGENT_AZURE_API_KEY"],
            reason=_("env.azure.api_key", default="Azure OpenAI API key."),
        )
        missing += _require(
            ["UAGENT_AZURE_API_VERSION"],
            reason=_("env.azure.api_version", default="Azure OpenAI API version (e.g., 2024-xx-xx)."),
        )
    elif provider == "openai":
        missing += _require(
            ["UAGENT_OPENAI_API_KEY"],
            reason=_("env.openai.api_key", default="OpenAI API key."),
        )
    elif provider == "bedrock":
        missing += _require(
            ["UAGENT_BEDROCK_BASE_URL"],
            reason=_("env.bedrock.base_url", default="Bedrock proxy endpoint/base URL (OpenAI-compatible)."),
        )
        missing += _require(
            ["UAGENT_BEDROCK_API_KEY"],
            reason=_("env.bedrock.api_key", default="Bedrock proxy API key (OpenAI-compatible)."),
        )
    elif provider == "openrouter":
        missing += _require(
            ["UAGENT_OPENROUTER_API_KEY"],
            reason=_("env.openrouter.api_key", default="OpenRouter API key."),
        )
    elif provider == "grok":
        missing += _require(
            ["UAGENT_GROK_API_KEY"],
            reason=_("env.grok.api_key", default="Grok (xAI) API key."),
        )
    elif provider == "gemini":
        missing += _require(
            ["UAGENT_GEMINI_API_KEY"],
            reason=_("env.gemini.api_key", default="Gemini API key."),
        )
        try:
            from google import genai as _genai  # noqa: F401
        except Exception:
            warnings.append(
                _(
                    "env.warn.google_genai",
                    default="Python package 'google-genai' is not installed. Provider=gemini requires it.",
                )
            )
    elif provider == "claude":
        missing += _require(
            ["UAGENT_CLAUDE_API_KEY"],
            reason=_("env.claude.api_key", default="Anthropic (Claude) API key."),
        )
        try:
            from anthropic import Anthropic as _Anthropic  # noqa: F401
        except Exception:
            warnings.append(
                _(
                    "env.warn.anthropic",
                    default="Python package 'anthropic' is not installed. Provider=claude requires it.",
                )
            )
    elif provider == "nvidia":
        missing += _require(
            ["UAGENT_NVIDIA_API_KEY"],
            reason=_("env.nvidia.api_key", default="NVIDIA API key."),
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
            "env.fatal.header",
            default=f"[FATAL] Environment validation failed ({context}).",
            context=context,
        )
    )
    if missing:
        lines.append(_("env.fatal.missing", default="Missing required environment variables:"))
        for m in missing:
            lines.append(
                _(
                    "env.fatal.item",
                    default=f"- {m.name}: {m.reason}",
                    name=m.name,
                    reason=m.reason,
                )
            )
    if warnings:
        lines.append(_("env.fatal.warnings", default="Warnings:"))
        for w in warnings:
            lines.append(f"- {w}")
    lines.append("")
    lines.append(_("env.fix.title", default="How to fix:"))
    lines.append(
        _(
            "env.fix.one",
            default="- Set the variables above in your environment before starting the program.",
        )
    )
    lines.append(
        _(
            "env.fix.two",
            default="- You can set them via your OS environment settings, a .env file, your shell startup scripts,",
        )
    )
    lines.append(
        _(
            "env.fix.three",
            default="  or your process manager / service configuration (CI secrets, systemd, Docker, etc.).",
        )
    )
    return "\n".join(lines) + "\n"
