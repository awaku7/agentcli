"""Shared configuration for UAG decision providers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

SUPPORTED_DECISION_PROVIDERS = ("none", "typesafe", "openrouter", "openai", "laya")


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

    if str(env.get("UAGENT_PROVIDER") or "").strip().lower() == "openai":
        return DecisionSettings(provider="openai", source="provider_default")

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
            "Overrides UAGENT_DECISION_PROVIDER; defaults to OpenAI Decisions "
            "when UAGENT_PROVIDER=openai, otherwise none."
        ),
    )
    return parser
