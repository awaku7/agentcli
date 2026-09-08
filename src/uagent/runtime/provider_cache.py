"""Provider-neutral cache planning for Active Context projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CacheAction = Literal["REUSE", "REBUILD", "REANCHOR", "BYPASS", "NONE"]


@dataclass(frozen=True)
class ProviderCachePlan:
    """Describe how a provider should handle a changed context projection."""

    provider: str
    model: str
    action: CacheAction
    projection_changed: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "action": self.action,
            "projection_changed": self.projection_changed,
            "reason": self.reason,
        }


def plan_provider_cache(
    *,
    provider: str,
    model: str,
    projection_changed: bool,
    previous_response_id: bool = False,
) -> ProviderCachePlan:
    """Return a provider-specific cache action for one Active Context build.

    The runtime makes one decision; provider adapters implement the action:
    Gemini/Vertex use named caches, Claude uses cache-control breakpoints, and
    Responses providers may need to bypass a previous response chain.
    """
    name = (provider or "").strip().lower()
    if not projection_changed:
        return ProviderCachePlan(name, model, "REUSE", False, "projection unchanged")
    if name in {"gemini", "vertexai"}:
        return ProviderCachePlan(
            name, model, "REBUILD", True, "Active Context projection changed"
        )
    if name == "claude":
        return ProviderCachePlan(
            name, model, "REANCHOR", True, "reapply cache_control breakpoints"
        )
    if name in {"openai", "azure"} and previous_response_id:
        return ProviderCachePlan(
            name, model, "BYPASS", True, "previous response chain no longer matches"
        )
    return ProviderCachePlan(name, model, "NONE", True, "provider cache not managed")


__all__ = ["CacheAction", "ProviderCachePlan", "plan_provider_cache"]
