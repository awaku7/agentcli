"""Lazy decision-provider factory."""

from __future__ import annotations

import importlib
from typing import Any

from .base import DecisionProvider
from .settings import DecisionSettings, get_decision_settings

_ADAPTERS: dict[str, tuple[str, str]] = {
    "typesafe": ("uagent.decision.typesafe", "TypeSafeDecisionProvider"),
    "laya": ("uagent.decision.laya", "LayaDecisionProvider"),
}


class DecisionProviderUnavailableError(RuntimeError):
    """Raised when an explicitly selected adapter cannot be created."""


def create_decision_provider(
    settings: DecisionSettings | None = None,
    **adapter_kwargs: Any,
) -> DecisionProvider | None:
    """Create the selected adapter lazily.

    The none provider is represented by absence of an active provider so the
    default path does not import or initialize provider-specific code.
    """

    resolved = settings or get_decision_settings()
    if resolved.provider == "none":
        return None

    module_name, class_name = _ADAPTERS[resolved.provider]
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise DecisionProviderUnavailableError(
            f"Decision provider '{resolved.provider}' is selected but its adapter "
            f"is unavailable: {exc.name or module_name}."
        ) from exc

    provider_class = getattr(module, class_name, None)
    if provider_class is None:
        raise DecisionProviderUnavailableError(
            f"Decision provider '{resolved.provider}' adapter does not expose "
            f"{class_name}."
        )

    return provider_class(settings=resolved, **adapter_kwargs)
