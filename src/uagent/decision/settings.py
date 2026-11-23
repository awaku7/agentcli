"""Shared configuration for UAG decision providers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SUPPORTED_DECISION_PROVIDERS = (
    "none",
    "auto",
    "typesafe",
    "openrouter",
    "openai",
    "google",
    "laya",
)


class DecisionConfigurationError(ValueError):
    """Raised when decision-provider configuration is invalid."""


@dataclass(frozen=True)
class DecisionSettings:
    """Resolved process-wide decision-provider settings."""

    provider: str = "none"
    source: str = "default"

    def __post_init__(self) -> None:
        if self.provider not in SUPPORTED_DECISION_PROVIDERS:
            raise DecisionConfigurationError(
                "Unsupported decision provider: " + str(self.provider)
            )

    @property
    def enabled(self) -> bool:
        return self.provider != "none"


_current_settings = DecisionSettings()


def normalize_decision_provider(value: Any) -> str:
    """Normalize and validate a provider key."""

    raw = str(value or "").strip().lower() or "none"
    if raw not in SUPPORTED_DECISION_PROVIDERS:
        supported = ", ".join(SUPPORTED_DECISION_PROVIDERS)
        raise DecisionConfigurationError(
            f"Unsupported decision provider '{raw}'. Expected one of: {supported}."
        )
    return raw


def default_decision_provider_for_llm(provider: Any) -> str | None:
    """Return the native Decisions adapter matching a main LLM provider."""

    normalized = str(provider or "").strip().lower()
    return {
        "openai": "openai",
        "gemini": "google",
        "google": "google",
    }.get(normalized)


def default_decision_model_for_llm(provider: Any) -> str | None:
    """Return a provider-native model ID when one has a built-in default."""

    normalized = str(provider or "").strip().lower()
    return {"azure": "Microsoft-Decision-1.1"}.get(normalized)


def resolve_decision_settings(
    *,
    cli_provider: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> DecisionSettings:
    """Resolve CLI > environment > default without initializing any adapter."""

    if cli_provider is not None and str(cli_provider).strip():
        return DecisionSettings(
            provider=normalize_decision_provider(cli_provider),
            source="cli",
        )

    env = os.environ if environ is None else environ
    raw_env = env.get("UAGENT_DECISION_PROVIDER")
    if raw_env is not None and str(raw_env).strip():
        return DecisionSettings(
            provider=normalize_decision_provider(raw_env),
            source="env",
        )

    provider_default = default_decision_provider_for_llm(env.get("UAGENT_PROVIDER"))
    if provider_default is not None:
        return DecisionSettings(provider=provider_default, source="provider_default")

    main_provider = str(env.get("UAGENT_PROVIDER") or "").strip().lower()
    if main_provider == "azure":
        decision_endpoint = str(env.get("UAGENT_DECISION_ENDPOINT") or "").strip()
        azure_endpoint = (
            str(env.get("UAGENT_AZURE_BASE_URL") or env.get("AZURE_ENDPOINT") or "")
            .strip()
            .lower()
        )
        # Azure OpenAI and Microsoft Foundry have different endpoints and
        # credentials. Only infer the Microsoft adapter when configuration
        # identifies a Foundry Decision endpoint/resource.
        if decision_endpoint or ".services.ai.azure.com" in azure_endpoint:
            return DecisionSettings(provider="auto", source="provider_default")

    return DecisionSettings()


def configure_decision_settings(
    *,
    cli_provider: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> DecisionSettings:
    """Resolve and store the process-wide decision-provider setting."""

    global _current_settings
    _current_settings = resolve_decision_settings(
        cli_provider=cli_provider,
        environ=environ,
    )
    return _current_settings


def get_decision_settings() -> DecisionSettings:
    """Return the most recently configured process-wide settings."""

    return _current_settings


def add_decision_provider_argument(parser: Any) -> Any:
    """Add the common opt-in decision-provider CLI argument to a parser."""

    parser.add_argument(
        "--decision-provider",
        dest="decision_provider",
        choices=SUPPORTED_DECISION_PROVIDERS,
        default=None,
        help=(
            "Select the dedicated decision provider. "
            "'auto' routes catalogued models using llmcapa protocol metadata. "
            "Overrides UAGENT_DECISION_PROVIDER; defaults to OpenAI Decisions "
            "for UAGENT_PROVIDER=openai, Google Decisions for gemini, and "
            "Microsoft Foundry Decisions for Azure when a Foundry endpoint is "
            "configured; otherwise none."
        ),
    )
    return parser
