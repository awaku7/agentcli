"""Runtime policy for provider-neutral context management."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_optional_int(name: str) -> int | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class ContextPolicy:
    """Single source of truth for context-management feature switches."""

    provider: str = ""
    model: str = ""
    budget_enabled: bool = True
    budget_chars: int = 100_000
    # The default is intentionally uncapped; bounded mode is opt-in.
    budget_unlimited: bool = True
    auto_retrieve: bool = True
    auto_state: bool = True
    tool_result_max_rows: int = 500
    budget_tokens: int | None = None

    @classmethod
    def from_environment(
        cls, *, provider: str = "", model: str = ""
    ) -> "ContextPolicy":
        provider_name = str(provider or "").strip().lower()
        provider_key = re.sub(r"[^a-z0-9]+", "_", provider_name).strip("_").upper()
        provider_budget_name = (
            f"UAGENT_CONTEXT_BUDGET_CHARS_{provider_key}" if provider_key else ""
        )
        budget_name = provider_budget_name or "UAGENT_CONTEXT_BUDGET_CHARS"
        mode = os.environ.get("UAGENT_CONTEXT_BUDGET_MODE", "unlimited").strip().lower()
        budget_unlimited = mode in {"unlimited", "none", "off", ""}
        return cls(
            provider=provider_name,
            model=str(model or "").strip(),
            budget_enabled=_env_bool("UAGENT_CONTEXT_BUDGET_ENABLED", True),
            budget_chars=_env_int(
                budget_name,
                _env_int("UAGENT_CONTEXT_BUDGET_CHARS", 100_000, 1),
                1,
            ),
            budget_unlimited=budget_unlimited,
            auto_retrieve=_env_bool("UAGENT_AUTO_RETRIEVE_TOOL_RESULTS", True),
            auto_state=_env_bool("UAGENT_AUTO_INJECT_AGENT_STATE", True),
            tool_result_max_rows=_env_int("UAGENT_TOOL_RESULT_MAX_ROWS", 500),
            budget_tokens=_env_optional_int("UAGENT_CONTEXT_BUDGET_TOKENS"),
        )


__all__ = ["ContextPolicy"]
