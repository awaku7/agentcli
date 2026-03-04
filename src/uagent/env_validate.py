# -*- coding: utf-8 -*-
"""env_validate.py

Centralized environment-variable validation.

Goal:
- Fail fast at startup with a clear, aggregated error message when required
  environment variables are missing or invalid.

Notes:
- Never print secrets (API keys). Only print variable names and brief guidance.
- This module is intentionally small and dependency-free.

Language policy:
- English only (as requested).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class MissingEnv:
    name: str
    reason: str


def _get(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _require(names: Sequence[str], reason: str) -> List[MissingEnv]:
    missing: List[MissingEnv] = []
    for n in names:
        if not _get(n):
            missing.append(MissingEnv(name=n, reason=reason))
    return missing


def detect_provider_allow_empty() -> str:
    """Return normalized provider name; empty string if not set."""
    return _get("UAGENT_PROVIDER").lower()


def validate_startup_env() -> Tuple[str, List[MissingEnv], List[str]]:
    """Validate environment variables required to start.

    Returns:
      (provider, missing, warnings)

    - provider: normalized provider name ("azure", "openai", ...), or "".
      If empty, missing will include UAGENT_PROVIDER.
    - missing: list of missing required env vars.
    - warnings: non-fatal messages.
    """

    missing: List[MissingEnv] = []
    warnings: List[str] = []

    provider = detect_provider_allow_empty()

    if not provider:
        # Provider is required. When it is missing, we also show *all* provider-specific
        # required variables as candidates, so users can see everything they may need
        # to set (depending on which provider they choose).
        missing += _require(
            ["UAGENT_PROVIDER"],
            reason="Required to select the LLM provider (azure/openai/openrouter/gemini/grok/claude/nvidia).",
        )

        # Candidate requirements for each provider (displayed only when provider is missing).
        missing += _require(
            [
                "UAGENT_AZURE_BASE_URL",
                "UAGENT_AZURE_API_KEY",
                "UAGENT_AZURE_API_VERSION",
            ],
            reason="(azure) Required when using Azure OpenAI.",
        )
        missing += _require(
            ["UAGENT_OPENAI_API_KEY"],
            reason="(openai) Required when using OpenAI.",
        )
        missing += _require(
            ["UAGENT_OPENROUTER_API_KEY"],
            reason="(openrouter) Required when using OpenRouter.",
        )
        missing += _require(
            ["UAGENT_GROK_API_KEY"],
            reason="(grok) Required when using Grok (xAI).",
        )
        missing += _require(
            ["UAGENT_GEMINI_API_KEY"],
            reason="(gemini) Required when using Gemini.",
        )
        missing += _require(
            ["UAGENT_CLAUDE_API_KEY"],
            reason="(claude) Required when using Claude (Anthropic).",
        )
        missing += _require(
            ["UAGENT_NVIDIA_API_KEY"],
            reason="(nvidia) Required when using NVIDIA.",
        )

        return provider, missing, warnings

    allowed = ("azure", "openai", "openrouter", "gemini", "grok", "claude", "nvidia")
    if provider not in allowed:
        # We intentionally do not hard-fail here because util_providers.detect_provider
        # already exits. This warning is just to make the message more informative.
        warnings.append(
            f"Unknown provider: {provider!r}. Allowed: {', '.join(allowed)} (startup will likely fail)."
        )
        return provider, missing, warnings

    # Provider-specific required vars (based on util_providers.make_client)
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
        missing += _require(["UAGENT_OPENAI_API_KEY"], reason="OpenAI API key.")
    elif provider == "openrouter":
        missing += _require(["UAGENT_OPENROUTER_API_KEY"], reason="OpenRouter API key.")
    elif provider == "grok":
        missing += _require(["UAGENT_GROK_API_KEY"], reason="Grok (xAI) API key.")
    elif provider == "gemini":
        missing += _require(["UAGENT_GEMINI_API_KEY"], reason="Gemini API key.")
        # Package presence is validated later in util_providers.make_client, but we warn early.
        try:
            from google import genai as _genai  # noqa: F401
        except Exception:
            warnings.append(
                "Python package 'google-genai' is not installed. Provider=gemini requires it."
            )
    elif provider == "claude":
        missing += _require(
            ["UAGENT_CLAUDE_API_KEY"], reason="Anthropic (Claude) API key."
        )
        try:
            from anthropic import Anthropic as _Anthropic  # noqa: F401
        except Exception:
            warnings.append(
                "Python package 'anthropic' is not installed. Provider=claude requires it."
            )
    elif provider == "nvidia":
        missing += _require(["UAGENT_NVIDIA_API_KEY"], reason="NVIDIA API key.")

    return provider, missing, warnings


def format_missing_env_message(
    *,
    missing: Sequence[MissingEnv],
    warnings: Sequence[str] = (),
    context: str = "startup",
) -> str:
    """Create a human-friendly fatal message (English only)."""

    lines: List[str] = []
    lines.append(f"[FATAL] Environment validation failed ({context}).")

    if missing:
        lines.append("Missing required environment variables:")
        for m in missing:
            lines.append(f"- {m.name}: {m.reason}")

    if warnings:
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("How to fix:")
    lines.append(
        "- Set the variables above in your environment before starting the program."
    )
    lines.append(
        "- You can set them via your OS environment settings, a .env file, your shell startup scripts,"
    )
    lines.append(
        "  or your process manager / service configuration (CI secrets, systemd, Docker, etc.)."
    )

    return "\n".join(lines) + "\n"
